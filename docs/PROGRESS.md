# Progress

## Current Step
Step 9.2 — Environment variable audit

## Completed Steps
- **Step 1.1** — Created full project directory tree: `backend/`, `frontend/`, `supabase/`, `docs/`
- **Step 1.2** — Created `CLAUDE.md` (project root) and `docs/PROGRESS.md`
- **Step 1.3** — Created `docs/PLAN.md` (all 9 phases, 34 steps with done-criteria) and `docs/ARCHITECTURE.md` (system diagram, 3 data flow diagrams, auth flow, design decisions table)
- **Step 1.4** — Created `docs/SCHEMA.md` (6 tables, HNSW index, cosine search function, ERD, storage bucket)
- **Step 1.5** — Created `backend/pyproject.toml`, `frontend/package.json`, `.env.example` (18 env vars across 6 integrations)
- **venv** — Created `backend/customer-agent` uv venv; 130 packages installed
- **Step 2.1** — Created `supabase/migrations/001_enable_pgvector.sql` and `002_documents.sql` (documents + document_chunks tables, HNSW index, hybrid_search_chunks + exact_search_chunks functions)
- **Step 2.2** — Created `supabase/migrations/003_conversations.sql` (conversations, messages, escalated_tickets, knowledge_gaps)
- **Step 2.3** — Created `004_rls.sql` (RLS policies for all 6 tables) and `005_storage.sql` (documents bucket, 50MB limit, PDF/DOCX/TXT only, per-user folder policies)
- **Step 2.4** — Created `backend/scripts/test_connection.py`; all 6 tables reachable, insert/read/delete cycle passed — "Connection OK"
- **Step 3.1** — Created `app/ingestion/loaders.py` (PDF/DOCX/TXT) and `app/ingestion/chunker.py` (RecursiveCharacterTextSplitter, 800/100); test produced 14 chunks — "Loaders OK"
- **Step 3.2** — Created `app/core/settings.py` (Pydantic Settings) and `app/ingestion/embedder.py` (OpenAI text-embedding-3-small, batch embed + pgvector insert); test verified non-null embeddings — "Embedder OK"
- **Step 3.3** — Created `app/ingestion/pipeline.py` (load → chunk → embed → store, PDF page tracking, chunk_count update); 4 chunks stored with correct FK — "Pipeline OK"
- **Step 3.4** — Created `app/main.py`, `app/api/deps.py`, `app/api/routes/ingest.py`; POST /ingest with JWT auth, file type detection, temp file handling; test returned chunk_count=1 — "Ingest endpoint OK"
- **Step 4.1** — Created `app/agent/tools/document_scope.py` (DocumentScopeTool, BaseTool subclass); test returned correct doc list with categories — "DocumentScopeTool OK"
- **Step 4.2** — Created `app/agent/tools/retriever.py` (RetrieverTool: query routing, rewriting, hybrid search RRF, cross-encoder rerank); semantic + exact_lookup paths verified — "RetrieverTool OK"
- **Step 4.3** — Created `app/agent/tools/escalation.py` (EscalationTool: logs to `knowledge_gaps`, creates Linear ticket, records `escalated_tickets`); both DB rows verified, Linear gracefully skipped when unconfigured — "EscalationTool OK"
- **Step 4.4** — Added Slack webhook + Resend email to EscalationTool; concurrent `asyncio.gather`; each integration independently graceful — code written, **test not yet run**
- **Step 4.4**
 — Added Slack webhook + Resend email to EscalationTool; concurrent `asyncio.gather`; each integration independently graceful — "EscalationTool OK"
- **Step 4.5** — Added Crisp live-chat handoff to EscalationTool (`_handoff_to_crisp`: creates conversation, posts operator note, returns inbox URL); wired into concurrent gather alongside Slack/Resend; three new settings fields (`crisp_website_id`, `crisp_identifier`, `crisp_key`); all 6 actions independently graceful — "EscalationTool OK"
- **Step 9.1** — Created `EmptyState` component + `error.tsx` global boundary; added `<Toaster richColors />` to root layout; wired `toast.success/error` into DocumentUploader (replaced inline status), document delete, and chat send error; swapped plain-text empty states in all three list tables for `EmptyState`; added hard rule #13 to system prompt preventing topic-labelled escalation messages; `tsc --noEmit` clean
- **Step 8.4** — Added delete button to `src/app/(dashboard)/admin/documents/page.tsx` (`handleDelete` deletes documents row, ON DELETE CASCADE removes chunks automatically; `deletingId` state disables button during in-flight request); `tsc --noEmit` clean
- **Step 8.3** — Created `src/components/admin/KnowledgeGapsTable.tsx` (question, count, last_seen columns) and `src/app/(dashboard)/admin/knowledge-gaps/page.tsx` (fetches `GET /admin/knowledge-gaps` with Bearer token, renders sorted table); `tsc --noEmit` clean
- **Step 8.2** — Created `src/app/(dashboard)/admin/escalations/[id]/page.tsx` (loads escalation from Supabase by ID, loads conversation history from `GET /conversations/{id}`, renders metadata card with status badge + Linear link + timestamps, and full conversation thread via `MessageList`); exported `StatusBadge` from `EscalationsTable.tsx` for reuse; `tsc --noEmit` clean
- **Step 8.1** — Created `src/components/admin/EscalationsTable.tsx` (status badge with yellow/green/gray, Linear ticket link, rows link to detail page) and `src/app/(dashboard)/admin/escalations/page.tsx` (fetches `GET /admin/escalations` with Bearer token, renders table); `tsc --noEmit` clean
- **Step 7.5** — Created `src/components/admin/DocumentUploader.tsx` (drag-and-drop + click-to-browse, optional category, optimistic button state, success/error feedback) and `src/app/(dashboard)/admin/documents/page.tsx` (upload section + document list table queried from Supabase, refreshes after each upload); middleware already guards `/admin`; `tsc --noEmit` clean
- **Step 7.4** — Replaced hardcoded sample data with live API calls: `chat/page.tsx` loads conversations from Supabase (RLS-scoped), auto-selects/creates the first conversation on mount, sends messages via `POST /chat` with Bearer token, loads history via `GET /conversations/{id}`, shows optimistic user bubble + ThinkingIndicator while waiting, replaces loading bubble with real answer + source citations, updates conversation title from first user message — `tsc --noEmit` clean
- **Step 7.3** — Created `src/types/chat.ts` (shared `Message`/`Source` interfaces); `SourceCitation` (document badge with page number); `MessageList` (auto-scroll, bouncing `ThinkingIndicator` for loading state, `whitespace-pre-wrap` for formatted answers, source badges below assistant messages); `MessageInput` (auto-resize textarea, Enter to send / Shift+Enter for newline); `chat/page.tsx` (sidebar with conversations + sign-out, main chat area, all wired with hardcoded sample data including loading state) — `tsc --noEmit` clean, middleware redirect verified
- **Step 7.2** — Created `src/middleware.ts` (guards `/chat` and `/admin/*`, redirects unauthenticated users to `/login`, redirects authenticated users away from auth routes); created `(auth)/login/page.tsx` and `(auth)/signup/page.tsx` (client components, email+password, error display, email confirmation flow); `GET /chat` unauthenticated → `307 /login` verified — "Auth pages OK"
- **Step 7.1** — Scaffolded Next.js 14 App Router project (TypeScript strict, Tailwind, ESLint); created `src/lib/supabase/client.ts` (`createBrowserClient`) and `src/lib/supabase/server.ts` (`createServerClient` with `getAll`/`setAll` cookie methods); `.env.local` wired to Supabase project; `npm run dev` ready in 4.4s, `tsc --noEmit` clean — "Next.js init OK"
- **Step 6.3** — Created `supabase/migrations/007_admin_functions.sql` (`get_knowledge_gap_summary`, `get_knowledge_gap_count`); created `app/api/routes/admin.py` (`GET /admin/escalations` with status filter + pagination, `GET /admin/knowledge-gaps` frequency-sorted via SQL GROUP BY); updated `main.py` to include admin router, tighten CORS to `settings.allowed_origins`, add `RequestValidationError` + `Exception` global handlers (structured JSON 500, not raw traceback); added `allowed_origins: list[str]` to `settings.py` — "Admin endpoints OK"
- **Step 6.2** — Created `app/api/schemas.py` (shared `SourceRef`), `app/db/__init__.py`, `app/db/messages.py` (`save_messages` batch-inserts user+assistant turns, `get_messages`); updated `chat.py` to persist every turn + cache hits; created `GET /conversations/{id}` in `conversations.py`; 2-turn exchange returned 4 rows in order with source citations — "Conversation persistence OK"
- **Step 6.1** — Created `app/api/routes/chat.py` (POST /chat: JWT auth, conversation ownership check, SemanticCache check/store, history load from DB, `graph.ainvoke()`, source extraction from retriever ToolMessages); added `get_graph()` lru_cache singleton + `get_openai_client()` to `deps.py`; cold call returns cited answer, warm call returns cache hit — "POST /chat OK"
- **Step 5.3** — Added `checkpointer: BaseCheckpointSaver | None = None` to `build_graph()` (passed to `builder.compile()`); `MemorySaver` used in test so the graph holds state between turns via `thread_id`; Turn 2 "backup codes" follow-up answered purely from conversation context (agent said "based on the documentation I already retrieved") — "Multi-turn memory OK"
- **Step 5.2** — Created `scripts/test_agent.py`; ingests a small TXT fixture then runs 3 scenarios: (1) password reset → retriever called once, answered from docs; (2) password requirements + 2FA setup → retriever called 2x, both topics answered; (3) enterprise pricing → not in KB → retriever×2 + document_scope + escalation → knowledge_gaps + escalated_tickets rows verified — "ReAct agent OK"
- **Step 5.1** — Created `app/agent/graph/state.py` (`AgentState` TypedDict: messages + conversation_id + user_id), `app/agent/graph/nodes.py` (`make_agent_node` closure factory + system prompt), `app/agent/graph/agent.py` (`build_graph()`: wires DocumentScope + Retriever + Escalation tools, LLM bind_tools, conditional edge on tool_calls, ToolNode prebuilt); graph compiled + agent invoked with empty KB → correctly called retriever → document_scope → escalation — "ReAct graph OK"
- **Step 4.6** — Created `supabase/migrations/006_semantic_cache.sql` (`semantic_cache` table, HNSW index, `search_semantic_cache()` function) and `app/agent/cache.py` (SemanticCache: full LLM response cache, user-scoped, similarity threshold=0.45, TTL); all hits/misses/cross-user-isolation verified — "SemanticCache OK"

## Pending Steps
9.2, 9.3, 9.4
9.1, 9.2, 9.3, 9.4

## Decisions Log
- **CLAUDE.md placement:** project root (not `docs/`) so Claude Code auto-discovers it every session.
- **PROGRESS.md placement:** `docs/` alongside all other planning files.
- **Folder structure:** `(auth)` and `(dashboard)` are Next.js route groups — share layout without appearing in the URL. Backend follows layered FastAPI convention: routes → agent/db, never reverse.
- **LLM model:** `claude-haiku-4-5-20251001` — latest Haiku, fast and cost-efficient for support use case.
- **Embeddings:** switched from HuggingFace all-mpnet-base-v2 (768-dim, local) to OpenAI text-embedding-3-small (1536-dim, API). Better quality; negligible cost at this scale.
- **Hybrid search:** dense (HNSW cosine) + sparse (Postgres tsvector BM25) merged via Reciprocal Rank Fusion. Handles both paraphrased questions and exact technical terms.
- **Re-ranker:** local cross-encoder `ms-marco-MiniLM-L-6-v2` re-scores top-20 hybrid candidates → top-5. No API cost; ~85MB model.
- **Query routing:** Claude Haiku classifies each sub-question as `exact_lookup` (verbatim text retrieval via BM25 only) or `semantic` (hybrid search + re-rank). Exact path skips vector search entirely.
- **Query rewriting:** Claude Haiku rewrites semantic queries before embedding — expands acronyms, adds context, clarifies intent.

## Gotchas
_None yet._
