# Quro — Enterprise Customer Support Agent

An agentic RAG system where companies upload product documentation and customers get instant, cited answers from a Claude-powered AI agent. When the agent cannot answer, it automatically escalates to the human support team via Linear, Slack, and email.

---

## Highlights

### LangGraph ReAct Agent with Input Guard
The agent isn't a simple prompt-response chain — it runs a full **ReAct loop** (Reason + Act) using LangGraph. Before every message reaches the agent, a lightweight **input guard** (a separate Haiku classifier) screens it for off-topic requests, prompt injection attempts, and abuse. Only messages classified as `safe` or `human_requested` proceed; everything else gets a canned response immediately, with zero LLM cost.

### Hybrid Search + Cross-Encoder Re-ranking
Retrieval uses **two signals in parallel**: dense vector search (pgvector cosine similarity with HNSW index) and sparse keyword search (PostgreSQL `tsvector` BM25). The results are merged with **Reciprocal Rank Fusion (RRF)** — a technique that combines ranked lists without needing score normalisation. The top-20 merged candidates are then re-scored by a **local cross-encoder** (`ms-marco-MiniLM-L-6-v2`) that reads the full query-chunk pair, not just embeddings. No API cost, no external re-ranking service.

### Query Routing and Rewriting
Each retrieval request goes through a **two-step pre-processing pipeline** before hitting the vector store:
1. **Routing** — Haiku classifies the query as `exact_lookup` (verbatim technical terms, error codes) or `semantic` (natural language intent). Exact lookups skip vector search entirely and go straight to BM25.
2. **Rewriting** — semantic queries are rewritten by Haiku to expand acronyms, add context, and improve embedding quality before the search.

### Full-Response Semantic Cache
Repeated or similar questions skip the LLM entirely. The cache stores full assistant responses keyed by query embedding similarity. Hits are **user-scoped** — one tenant's cached answer never surfaces for another. Threshold and TTL are configurable; the cache uses the same pgvector HNSW index as retrieval.

### Five-Channel Escalation (Concurrent, Independently Graceful)
When the agent exhausts retrieval, it calls the escalation tool which fires **five actions concurrently** via `asyncio.gather`:
1. Logs the question to `knowledge_gaps`
2. Creates a **Linear** ticket
3. Inserts an `escalated_tickets` row
4. Posts a **Slack** webhook notification
5. Sends a **Resend** email to the support team
6. Opens a **Crisp** live-chat conversation

Each integration is independently optional — a missing env var logs a warning and skips that channel without failing the others.

### Knowledge Gap Tracking
Every unanswered question is persisted to a `knowledge_gaps` table. The admin dashboard surfaces these grouped by question text, sorted by frequency, so teams know exactly which documentation to add next to reduce escalation volume.

### Ticket Status Loop
When an admin updates an escalation ticket status (Open → In Progress → Resolved), the agent knows about it. If a user returns to the same conversation and asks "what happened to my ticket?", the agent calls the `ticket_status` tool and reports the current status in real time — closing the feedback loop without leaving the chat.

### Row-Level Security Throughout
Every Supabase table has **RLS policies** enforced at the database level. Users can only read and write their own conversations and messages — not enforced in application code, enforced in Postgres.

---

## What it does

**For admins:**
- Upload PDF, DOCX, or TXT product documentation
- Documents are chunked, embedded, and stored in a pgvector knowledge base
- View all escalated support tickets with full conversation history and status management
- Track knowledge gaps — questions the agent couldn't answer, sorted by frequency

**For users:**
- Chat with a Claude-powered support agent that answers from the knowledge base
- Every answer includes source citations (document name + page number)
- If the agent can't answer after two retrieval attempts, it escalates automatically and creates a Linear ticket

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript strict, Tailwind CSS |
| Backend | FastAPI (Python 3.12), async throughout |
| Agent | LangGraph ReAct loop with tool use |
| LLM | Claude Haiku (claude-haiku-4-5) via Anthropic API |
| Embeddings | OpenAI text-embedding-3-small (1536-dim) |
| Vector search | Supabase pgvector — hybrid dense + sparse (BM25) with RRF |
| Re-ranking | Cross-encoder ms-marco-MiniLM-L-6-v2 (local, no API cost) |
| Semantic cache | Full-response cache — repeated questions skip the LLM entirely |
| Database & Auth | Supabase (PostgreSQL + Row Level Security + Supabase Auth) |
| Storage | Supabase Storage (document files) |
| Escalation | Linear + Slack + Resend (email) + Crisp (live chat) |

---

## Demo

The login page has a one-click **Login as Admin** button for reviewing the admin panel without signing up.

| Path | What you see |
|---|---|
| **Admin** (one-click) | Upload documents, manage the knowledge base, view escalated tickets, track knowledge gaps |
| **User** (sign up) | Chat with the AI support agent, receive cited answers, trigger escalations |

> **Note on roles:** In a real deployment, admin access is controlled by setting `{ role: "admin" }` in a user's Supabase `app_metadata` (writable only by the service role). The demo uses a pre-configured admin account so reviewers can explore the admin panel without an invite flow. Regular users sign up via the standard form.

---

## Running locally

### Prerequisites
- Python 3.12 + [uv](https://docs.astral.sh/uv/)
- Node.js 18+
- A Supabase project
- Anthropic API key
- OpenAI API key (embeddings only)

### 1. Clone and install

```bash
git clone <repo-url>
cd Customer-Support-Agent---Quro

# Backend
cd backend
uv sync

# Frontend
cd ../frontend
npm install
```

### 2. Environment variables

```bash
cp .env.example .env
# Fill in all values — see comments in .env.example
```

For the frontend, create `frontend/.env.local`:
```
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
NEXT_PUBLIC_API_URL=http://localhost:8000

# Optional: enables the "Login as Admin" demo button
NEXT_PUBLIC_DEMO_ADMIN_EMAIL=admin@yourdomain.com
NEXT_PUBLIC_DEMO_ADMIN_PASSWORD=...
```

### 3. Run the database migrations

Run each file in `supabase/migrations/` in order in the Supabase SQL editor.

### 4. Start the servers

```bash
# Terminal 1 — Backend
cd backend
uv run uvicorn app.main:app --reload

# Terminal 2 — Frontend
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## Project structure

```
├── backend/
│   └── app/
│       ├── agent/          # LangGraph ReAct graph, tools, semantic cache
│       ├── api/            # FastAPI routes (chat, ingest, admin, conversations)
│       ├── db/             # Message persistence helpers
│       └── ingestion/      # PDF/DOCX/TXT loaders, chunker, embedder, pipeline
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── (auth)/     # Login + signup pages
│       │   ├── (dashboard)/# Admin panel (documents, escalations, knowledge gaps)
│       │   └── chat/       # Customer chat interface
│       └── components/     # Shared UI components
├── supabase/
│   └── migrations/         # All schema + RLS migrations in order
└── docs/                   # Architecture, schema, and progress docs
```
