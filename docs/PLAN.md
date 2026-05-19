# Plan — Enterprise Customer Support Agent

Every phase and every step. For each step: what gets built, which files are created or
modified, and how to verify the step is done.

---

## PHASE 1 — Project Setup

### Step 1.1 — Folder structure
**Builds:** Empty directory tree for the entire project.
**Files created:** None (directories only).
**Done when:** `find . -type d` shows the full tree with backend, frontend, supabase, docs.

### Step 1.2 — CLAUDE.md and PROGRESS.md
**Builds:** Session memory files.
**Files created:** `CLAUDE.md`, `docs/PROGRESS.md`.
**Done when:** Both files exist and contain all required sections.

### Step 1.3 — PLAN.md and ARCHITECTURE.md
**Builds:** Full project plan and system architecture document.
**Files created:** `docs/PLAN.md`, `docs/ARCHITECTURE.md`.
**Done when:** Both files exist; ARCHITECTURE.md includes all three data flow diagrams.

### Step 1.4 — SCHEMA.md
**Builds:** Database schema reference document.
**Files created:** `docs/SCHEMA.md`.
**Done when:** All tables, columns, types, constraints, and pgvector SQL are documented.

### Step 1.5 — Dependency files
**Builds:** Package manifests and environment variable template.
**Files created:** `backend/pyproject.toml`, `frontend/package.json`, `.env.example`.
**Done when:** `uv sync` runs without errors in `backend/`; `.env.example` lists every
required key with a comment explaining its purpose.

---

## PHASE 2 — Supabase Setup

### Step 2.1 — pgvector + documents tables
**Builds:** SQL migration to enable pgvector and create `documents` and `document_chunks`.
**Files created:** `supabase/migrations/001_enable_pgvector.sql`,
`supabase/migrations/002_documents.sql`.
**Done when:** Migration runs cleanly in Supabase SQL editor; `document_chunks` has a
`embedding vector(768)` column and a cosine similarity index.

### Step 2.2 — Remaining tables
**Builds:** SQL for `conversations`, `messages`, `escalated_tickets`, `knowledge_gaps`.
**Files created:** `supabase/migrations/003_conversations.sql`.
**Done when:** All four tables exist in Supabase with correct foreign key relationships.

### Step 2.3 — RLS policies and storage bucket
**Builds:** Row Level Security policies for all tables; Supabase Storage bucket for docs.
**Files created:** `supabase/migrations/004_rls.sql`, `supabase/migrations/005_storage.sql`.
**Done when:** Anonymous reads are blocked; authenticated users can only access their own
conversations; storage bucket `documents` exists with correct policies.

### Step 2.4 — Connection test script
**Builds:** Python script that insert/read/delete a row to prove the Supabase connection works.
**Files created:** `backend/scripts/test_connection.py`.
**Done when:** `uv run backend/scripts/test_connection.py` prints "Connection OK" with no
errors.

---

## PHASE 3 — Ingestion Pipeline

### Step 3.1 — File loaders and chunker
**Builds:** Functions to extract text from PDF, DOCX, and TXT files, then chunk with
LangChain's SemanticChunker.
**Files created:** `backend/app/ingestion/loaders.py`, `backend/app/ingestion/chunker.py`.
**Done when:** `uv run` test script loads a sample file of each type and prints chunk count.

### Step 3.2 — Embedder and pgvector storage
**Builds:** Function that embeds a list of text chunks using all-mpnet-base-v2 and stores
vectors in Supabase `document_chunks`.
**Files created:** `backend/app/ingestion/embedder.py`.
**Done when:** Running the test stores one chunk in Supabase; row is visible in the
Supabase dashboard with a non-null embedding column.

### Step 3.3 — End-to-end ingest() function
**Builds:** Single `ingest()` function that wires loaders → chunker → embedder into one
pipeline.
**Files created/modified:** `backend/app/ingestion/pipeline.py`.
**Done when:** `uv run` test script takes a sample PDF, calls `ingest()`, and the resulting
chunks appear in `document_chunks` with correct `document_id` foreign keys.

### Step 3.4 — POST /ingest endpoint
**Builds:** FastAPI app with a file-upload endpoint that calls `ingest()`.
**Files created:** `backend/app/main.py`, `backend/app/api/routes/ingest.py`.
**Done when:** `curl -F "file=@sample.pdf" http://localhost:8000/ingest` returns a JSON
response with chunk count; chunks appear in Supabase.

---

## PHASE 4 — LangGraph Agent Tools

### Step 4.1 — document_scope_tool
**Builds:** Tool that queries Supabase for all distinct document names and categories.
**Files created:** `backend/app/agent/tools/document_scope.py`.
**Done when:** Standalone test returns correct document metadata for what is in Supabase.

### Step 4.2 — retriever_tool
**Builds:** Tool that embeds a query string and searches `document_chunks` via cosine
similarity. Returns top-k chunks with source name and page number.
**Files created:** `backend/app/agent/tools/retriever.py`.
**Done when:** Test query against ingested documents returns relevant chunks with correct
source citations.

### Step 4.3 — escalation_tool (Supabase + Linear)
**Builds:** Tool that logs to `knowledge_gaps` table and creates a Linear ticket.
**Files created:** `backend/app/agent/tools/escalation.py`.
**Done when:** Test call inserts a row in `knowledge_gaps` and a ticket appears in Linear.

### Step 4.4 — escalation_tool (+ Slack + Resend)
**Builds:** Adds Slack webhook notification and Resend email to the escalation tool.
**Files modified:** `backend/app/agent/tools/escalation.py`.
**Done when:** Test call triggers all four actions (Linear + Slack + Resend + Supabase);
missing env vars cause a logged warning, not a crash.

### Step 4.5 — escalation_tool (+ Crisp)
**Builds:** Adds Crisp live chat handoff as the fifth escalation action.
**Files modified:** `backend/app/agent/tools/escalation.py`.
**Done when:** Full escalation test triggers all five integrations; each one logs
success or a graceful failure independently.

### Step 4.6 — Semantic Cache
**Builds:** Full-response semantic cache that lets the chat route skip the LLM
entirely when a semantically similar question has already been answered.
User-scoped so one tenant's cached answers never appear for another tenant.
**Files created:** `supabase/migrations/006_semantic_cache.sql`,
`backend/app/agent/cache.py`.
**Wired into:** `POST /chat` at Step 6.1.
**Done when:** Test proves: (1) similar queries hit the cache after one store,
(2) unrelated query misses, (3) different user gets a miss (cross-user isolation).

---

## PHASE 5 — LangGraph Agent

### Step 5.1 — ReAct graph
**Builds:** LangGraph graph: state definition, agent node, tool node, conditional edges,
system prompt, tool binding to Claude.
**Files created:** `backend/app/agent/graph/state.py`,
`backend/app/agent/graph/agent.py`, `backend/app/agent/graph/nodes.py`.
**Done when:** `uv run` test script compiles the graph without errors and the agent can
answer a simple question using `retriever_tool`.

### Step 5.2 — Three-scenario agent test
**Builds:** Test script exercising: (1) single retriever call, (2) multi-step retrieval
with two sub-questions, (3) escalation trigger.
**Files created:** `backend/scripts/test_agent.py`.
**Done when:** All three scenarios complete without errors; escalation scenario creates a
Linear ticket.

### Step 5.3 — Conversation memory
**Builds:** Chat history passed into graph state so the agent can reference earlier turns.
**Files modified:** `backend/app/agent/graph/state.py`, `backend/app/agent/graph/agent.py`.
**Done when:** Multi-turn test: second message references first; agent incorporates prior
context in its answer.

---

## PHASE 6 — FastAPI Routes

### Step 6.1 — POST /chat
**Builds:** Endpoint that accepts `{message, conversation_id}`, runs the LangGraph agent,
returns `{answer, sources}`.
**Files created:** `backend/app/api/routes/chat.py`.
**Files modified:** `backend/app/main.py`.
**Done when:** `curl -X POST /chat` with a test question returns a cited answer.

### Step 6.2 — Conversation persistence
**Builds:** Saves every user message and agent response to `messages` table.
Adds `GET /conversations/{id}` to fetch history.
**Files created:** `backend/app/api/routes/conversations.py`.
**Files modified:** `backend/app/api/routes/chat.py`, `backend/app/db/`.
**Done when:** After a chat exchange, `GET /conversations/{id}` returns both turns in order.

### Step 6.3 — Admin endpoints + middleware
**Builds:** `GET /escalations`, `GET /knowledge-gaps`, CORS middleware, global error handler.
**Files created:** `backend/app/api/routes/admin.py`.
**Files modified:** `backend/app/main.py`.
**Done when:** Both admin endpoints return data; a deliberate 500 returns a structured
JSON error body, not a raw traceback.

---

## PHASE 7 — Next.js Frontend Setup

### Step 7.1 — Next.js init + Supabase client
**Builds:** Next.js 14 project (App Router, TypeScript strict, Tailwind). Supabase browser
and server clients configured.
**Files created:** All Next.js scaffold files; `frontend/src/lib/supabase/client.ts`,
`frontend/src/lib/supabase/server.ts`.
**Done when:** `npm run dev` starts without errors; Supabase client instantiates correctly.

### Step 7.2 — Auth pages
**Builds:** Login and signup pages using Supabase Auth. Middleware that redirects
unauthenticated users away from protected routes.
**Files created:** `frontend/src/app/(auth)/login/page.tsx`,
`frontend/src/app/(auth)/signup/page.tsx`, `frontend/src/middleware.ts`.
**Done when:** Signing up creates a Supabase user; logging in redirects to `/chat`;
visiting `/chat` while logged out redirects to `/login`.

### Step 7.3 — Chat UI (static)
**Builds:** Message list, message input, loading skeleton, source citation display.
Static — no API calls yet.
**Files created:** `frontend/src/components/chat/MessageList.tsx`,
`frontend/src/components/chat/MessageInput.tsx`,
`frontend/src/components/chat/SourceCitation.tsx`,
`frontend/src/app/chat/page.tsx`.
**Done when:** Chat page renders with hardcoded sample messages; source citations display
correctly; loading state is visible.

### Step 7.4 — Wire chat to API
**Builds:** Chat page calls `POST /chat`; streams or polls for response; displays answer
with source citations.
**Files modified:** `frontend/src/app/chat/page.tsx` and chat components.
**Done when:** Full user message → agent response flow works in browser with real FastAPI
backend running.

### Step 7.5 — Document upload page
**Builds:** File picker, upload to Supabase Storage, trigger `POST /ingest`, ingestion
status display.
**Files created:** `frontend/src/app/(dashboard)/admin/documents/page.tsx`,
`frontend/src/components/admin/DocumentUploader.tsx`.
**Done when:** Uploading a PDF triggers ingestion; chunks appear in Supabase; status
message confirms success or shows error.

---

## PHASE 8 — Admin Dashboard

### Step 8.1 — Escalated tickets list
**Builds:** Table of escalated conversations with status, timestamp, and title.
**Files created:** `frontend/src/app/(dashboard)/admin/escalations/page.tsx`,
`frontend/src/components/admin/EscalationsTable.tsx`.
**Done when:** Page renders real data from `GET /escalations`.

### Step 8.2 — Ticket detail page
**Builds:** Full conversation history for a selected ticket with a link to Linear.
**Files created:** `frontend/src/app/(dashboard)/admin/escalations/[id]/page.tsx`.
**Done when:** Clicking a row in the table navigates to the detail page with full history.

### Step 8.3 — Knowledge gaps page
**Builds:** List of unanswered questions from `knowledge_gaps`, sorted by frequency.
**Files created:** `frontend/src/app/(dashboard)/admin/knowledge-gaps/page.tsx`,
`frontend/src/components/admin/KnowledgeGapsTable.tsx`.
**Done when:** Page renders real data from `GET /knowledge-gaps`.

### Step 8.4 — Document management page
**Builds:** List of ingested documents with file type, upload date, and delete option.
**Files modified:** `frontend/src/app/(dashboard)/admin/documents/page.tsx`,
`frontend/src/components/admin/DocumentUploader.tsx`.
**Done when:** Document list renders; deleting a document removes its chunks from Supabase.

---

## PHASE 9 — Polish and Deploy

### Step 9.1 — Empty states, error boundaries, toasts
**Builds:** Empty state components for all list pages; React error boundaries; toast
notifications (success/error) for upload, chat send, and escalation.
**Files created/modified:** Various component files.
**Done when:** Every empty list shows a helpful message; every user action has feedback.

### Step 9.2 — Environment variable audit
**Builds:** Verified `.env.example` with all keys and comments. No hardcoded secrets.
**Files modified:** `.env.example`, any files with hardcoded values.
**Done when:** `grep -r "sk-" .` and `grep -r "eyJ" .` return no results in source files.

### Step 9.3 — Deploy FastAPI to Railway
**Builds:** Railway deployment with all environment variables set. Health check endpoint.
**Files created:** `backend/Dockerfile` (or Railway nixpacks config).
**Done when:** `curl https://<railway-url>/health` returns `{"status": "ok"}`.

### Step 9.4 — Deploy Next.js to Vercel
**Builds:** Vercel deployment wired to Railway backend URL via `NEXT_PUBLIC_API_URL`.
**Done when:** Full end-to-end test on production URLs: upload a doc, ask a question,
receive a cited answer.
