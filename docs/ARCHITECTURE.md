# Architecture — Enterprise Customer Support Agent

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Browser (User)                             │
│                       Next.js 14 (Vercel)                           │
│         TypeScript · React · Tailwind · Supabase Auth SDK           │
└───────────────────┬─────────────────────┬───────────────────────────┘
                    │ REST (fetch)         │ Supabase JS SDK
                    │                     │
         ┌──────────▼──────────┐  ┌───────▼───────────────────────────┐
         │   FastAPI Backend   │  │            Supabase                │
         │     (Railway)       │  │                                    │
         │                     │  │  ┌─────────┐  ┌─────────────────┐ │
         │  /ingest            │  │  │  Auth   │  │    Storage      │ │
         │  /chat              │  │  │  (JWT)  │  │  (PDF/DOCX/TXT) │ │
         │  /conversations     │  │  └─────────┘  └─────────────────┘ │
         │  /escalations       │  │  ┌──────────────────────────────┐ │
         │  /knowledge-gaps    │  │  │        PostgreSQL             │ │
         │                     │  │  │  documents                   │ │
         │  ┌───────────────┐  │  │  │  document_chunks (pgvector)  │ │
         │  │ LangGraph     │  │  │  │  conversations               │ │
         │  │ ReAct Agent   │  │  │  │  messages                    │ │
         │  │               │  │  │  │  escalated_tickets           │ │
         │  │ Tools:        │  │  │  │  knowledge_gaps              │ │
         │  │ - scope       │◄─┼──┼──┤                              │ │
         │  │ - retriever   │  │  │  └──────────────────────────────┘ │
         │  │ - escalation  │  │  └───────────────────────────────────┘
         │  └───────┬───────┘  │
         │          │          │
         └──────────┼──────────┘
                    │
         ┌──────────▼────────────────────────────────┐
         │          External Integrations             │
         │  Linear · Slack Webhook · Resend · Crisp   │
         └───────────────────────────────────────────┘
```

---

## Component Responsibilities

### Next.js Frontend
- Handles all UI: chat interface, document upload, admin dashboard.
- Uses Supabase Auth SDK directly for login/signup — no auth proxy through FastAPI.
- JWT from Supabase Auth is attached to every FastAPI request as `Authorization: Bearer <token>`.
- No business logic — it only renders data and calls the FastAPI API.

### FastAPI Backend
- Stateless Python server. Validates JWTs on every protected route.
- Owns the ingestion pipeline (loaders → chunker → embedder → Supabase storage).
- Owns the LangGraph agent lifecycle: creates the graph, injects conversation history, runs the agent, returns the answer.
- Never stores files — it receives them, processes them, and stores vectors/metadata to Supabase.

### LangGraph ReAct Agent
- Runs inside FastAPI (not as a separate service).
- The graph has two nodes: `agent` (Claude decides next action) and `tools` (executes the chosen tool).
- Claude is bound to three tools. It loops until it reaches a final answer or triggers escalation.
- Graph state carries: `messages` (full conversation history), `sources` (chunks collected so far).

### Supabase
- Single source of truth for all persistent data.
- pgvector stores 768-dimensional embeddings from all-mpnet-base-v2. Cosine similarity search is done via a Postgres function.
- Storage bucket `documents` holds original uploaded files (for audit trail — not used in retrieval).
- RLS ensures users can only query their own conversations.

### HuggingFace Embeddings (local)
- `all-mpnet-base-v2` runs in-process inside FastAPI.
- Used at ingest time (embed chunks before storage) and at query time (embed the sub-question before vector search).
- No external API call — model is downloaded once and cached locally.

---

## Data Flow 1: Document Upload and Ingestion

```
User selects file (browser)
        │
        ▼
Upload file to Supabase Storage bucket "documents"
        │
        ▼
POST /ingest  ──►  FastAPI receives file bytes
                        │
                        ▼
                   loader (PDF/DOCX/TXT)
                   extracts raw text + page numbers
                        │
                        ▼
                   SemanticChunker
                   splits text into semantically coherent chunks
                        │
                        ▼
                   HuggingFace all-mpnet-base-v2
                   embeds each chunk → float[768]
                        │
                        ▼
                   INSERT into documents (metadata)
                   INSERT into document_chunks (text + embedding + page_number)
                        │
                        ▼
                   Return { chunks_stored: N }
```

**Why SemanticChunker instead of fixed-size splitting:**
Fixed-size chunking (e.g. 512 tokens) can cut a sentence mid-thought. SemanticChunker
groups sentences by embedding similarity, so each chunk is a coherent unit of meaning.
This directly improves retrieval quality.

---

## Data Flow 2: Chat Message and Agent Response

```
User types message (browser)
        │
        ▼
POST /chat  { message, conversation_id }
        │
        ▼
FastAPI validates JWT, loads conversation history from Supabase
        │
        ▼
LangGraph graph is compiled and invoked with:
  - messages: [system_prompt, ...history, new_user_message]
  - sources: []
        │
        ▼
┌─────────────────── REACT LOOP ────────────────────────────┐
│                                                            │
│  Agent node (Claude)                                       │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ 1. Call document_scope_tool                         │  │
│  │    → learn what document categories exist           │  │
│  │                                                     │  │
│  │ 2a. If relevant docs exist:                         │  │
│  │     Break question into sub-questions               │  │
│  │     Call retriever_tool once per sub-question       │  │
│  │     Collect chunks, accumulate in graph state       │  │
│  │                                                     │  │
│  │ 2b. If no relevant docs exist:                      │  │
│  │     Call escalation_tool immediately                │  │
│  │                                                     │  │
│  │ 3. If retrieval returned empty results:             │  │
│  │     Retry once with rephrased query                 │  │
│  │     If still empty → escalation_tool               │  │
│  │                                                     │  │
│  │ 4. Synthesise final answer with source citations    │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                            │
└────────────────────────────────────────────────────────────┘
        │
        ▼
Save user message + agent response to Supabase messages table
        │
        ▼
Return { answer, sources: [{doc_name, page_number}] }
```

### Inside retriever_tool — Advanced RAG Pipeline

Each call to `retriever_tool` runs this pipeline internally:

```
Sub-question string (from agent)
        │
        ▼
┌─── Query Rewriter (Claude Haiku) ──────────────────────┐
│  Input:  raw sub-question                              │
│  Output: { type, rewritten_query }                     │
│                                                        │
│  type = "exact_lookup"                                 │
│    → customer wants verbatim text (error codes,        │
│      contract clauses, specific section text)          │
│                                                        │
│  type = "semantic"                                     │
│    → customer wants an explanation or solution         │
│      → rewrites query for better retrieval             │
│        (expands acronyms, adds context, clarifies)     │
└────────────────────────────────────────────────────────┘
        │
        ├── type = "exact_lookup" ──────────────────────────┐
        │                                                   │
        │   exact_search_chunks(rewritten_query)            │
        │   Pure BM25 (ts_rank_cd cover-density)            │
        │   → returns verbatim matching chunks              │
        │   → no re-ranking (BM25 order is final)           │
        │                                                   │
        └── type = "semantic" ─────────────────────────────┐│
                                                           ││
            OpenAI text-embedding-3-small                  ││
            embeds rewritten_query → float[1536]           ││
                    │                                      ││
                    ▼                                      ││
            hybrid_search_chunks(embedding, query_text)    ││
            ├── Dense leg:  HNSW cosine search (top 20)    ││
            └── Sparse leg: BM25 tsvector search (top 20)  ││
                    │  merged via RRF                       ││
                    ▼                                      ││
            Top 20 hybrid candidates                       ││
                    │                                      ││
                    ▼                                      ││
            Cross-encoder re-ranker                        ││
            (cross-encoder/ms-marco-MiniLM-L-6-v2)         ││
            scores each candidate against the query        ││
                    │                                      ││
                    ▼                                      ││
            Top 5 re-ranked chunks ◄──────────────────────┘│
                                   ◄───────────────────────┘
        │
        ▼
Return: [{ content, doc_name, page_number, score }]
```

**Why two separate paths:**
- Exact lookup (error 403, contract clause): BM25 finds literal keyword matches better
  than vector search, which might return semantically similar but textually different chunks.
- Semantic questions: hybrid + re-rank is more robust — vector search handles paraphrasing,
  BM25 handles technical terms, cross-encoder resolves conflicts between both signals.

---

## Data Flow 3: Escalation

```
Agent decides it cannot answer confidently
        │
        ▼
escalation_tool is called with:
  { question, conversation_history, conversation_id }
        │
        ├──► Supabase: INSERT into knowledge_gaps { question, conversation_id, timestamp }
        │
        ├──► Linear API: Create issue
        │    title: auto-generated from question
        │    description: full conversation history
        │    → returns linear_ticket_url
        │
        ├──► Slack Webhook: POST { summary, linear_ticket_url }
        │    → support team notified in channel
        │
        ├──► Resend API: Send email to support team
        │    subject: "Escalated: <question title>"
        │    body: conversation history + Linear link
        │
        └──► Crisp API: Initiate live chat handoff
             → conversation transitions to human agent on Crisp dashboard

Each integration is wrapped in try/except.
Failure of any one does NOT stop the others.
All outcomes (success or error) are logged.
        │
        ▼
INSERT into escalated_tickets {
  conversation_id,
  linear_ticket_url,
  status: "open",
  title: auto-generated
}
        │
        ▼
Agent returns:
  "I've escalated your question to the support team.
   You'll hear back via [channel]. Ticket: <linear_url>"
```

---

## Authentication Flow

```
Browser                    Supabase Auth               FastAPI
   │                            │                         │
   │── POST /auth/signup ───────►                         │
   │◄── { session: { access_token (JWT) } } ─────────────│
   │                            │                         │
   │── POST /chat ──────────────────────────────────────►│
   │   Authorization: Bearer <JWT>                        │
   │                            │                         │
   │                            │◄── verify JWT ──────────│
   │                            │─── { user_id } ────────►│
   │                            │                         │
   │◄───────────────────────────────── { answer } ────────│
```

FastAPI verifies the JWT with Supabase's public key (JWKS endpoint). No session state
is held server-side — every request is independently verified.

---

## Key Design Decisions

| Decision | Choice | Why |
|---|---|---|
| Agent runs inside FastAPI | In-process, not separate service | Simpler ops; the agent is stateless and has no scaling needs independent of the API |
| Embeddings via API | OpenAI text-embedding-3-small | Higher quality than local models; 1536-dim vectors; cost is negligible at support-doc scale |
| Cross-encoder runs locally | sentence-transformers in-process | No per-call API cost; ms-marco-MiniLM-L-6-v2 is fast (~85MB) and purpose-built for passage re-ranking |
| Hybrid search (dense + sparse) | pgvector HNSW + Postgres tsvector/BM25 | Vector search handles paraphrasing; BM25 handles exact technical terms; RRF merges both without tuning weights |
| Query rewriting | Claude Haiku | Fast, cheap; classifies exact_lookup vs semantic and rewrites query for better retrieval |
| pgvector over Pinecone/Weaviate | Supabase built-in | One less external service; transactional consistency between metadata and vectors |
| LangGraph over bare LangChain | LangGraph ReAct graph | Explicit graph state, controllable tool-calling loop, easy to add nodes (e.g. confidence scoring) later |
| Supabase Auth, not custom JWT | Supabase built-in | Handles refresh tokens, magic links, OAuth — no auth code to maintain |
| Escalation: 5 actions, all fire | Parallel, fail gracefully | Support team gets notified via whichever channels are configured; partial failure is not a user-visible error |
