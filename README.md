# Quro — Enterprise Customer Support Agent

An agentic RAG (Retrieval-Augmented Generation) system where companies upload product documentation and customers get instant, cited answers from an AI support agent. When the agent cannot answer, it automatically escalates to the human support team via Linear, Slack, and email.

---

## What it does

**For admins:**
- Upload PDF, DOCX, or TXT product documentation
- Documents are chunked, embedded, and stored in a pgvector knowledge base
- View all escalated support tickets and their full conversation history
- Track knowledge gaps — questions the agent couldn't answer, sorted by frequency — to know what documentation to add next

**For users:**
- Chat with a Claude-powered support agent that answers from the knowledge base
- Every answer includes source citations (document name + page number)
- If the agent can't answer after two retrieval attempts, it automatically escalates to the human team and creates a Linear ticket

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript strict, Tailwind CSS |
| Backend | FastAPI (Python 3.12), async throughout |
| Agent | LangGraph ReAct loop with tool use |
| LLM | Claude (claude-haiku-4-5) via Anthropic API |
| Embeddings | OpenAI text-embedding-3-small (1536-dim) |
| Vector search | Supabase pgvector — hybrid dense + sparse (BM25) with RRF |
| Re-ranking | Cross-encoder ms-marco-MiniLM-L-6-v2 (local, no API cost) |
| Semantic cache | Full-response cache — repeated questions skip the LLM entirely |
| Database & Auth | Supabase (PostgreSQL + Row Level Security + Supabase Auth) |
| Storage | Supabase Storage (document files) |
| Escalation | Linear (tickets) + Slack (webhook) + Resend (email) + Crisp (live chat) |

---

## Demo

The login page has two one-click demo buttons:

| Button | What you see |
|---|---|
| **Login as Admin** | Upload documents, manage the knowledge base, view escalated tickets, track knowledge gaps |
| **Login as User** | Chat with the AI support agent, receive cited answers, trigger escalations |

> **Note on roles:** In a real deployment, admin access is controlled by setting `{ role: "admin" }` in a user's Supabase `app_metadata` (writable only by the service role — not by the user themselves). The demo uses two pre-configured accounts to let reviewers explore both sides of the product without needing an invite flow.

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
cd customer-support-agent

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

# Optional: enables demo login buttons
NEXT_PUBLIC_DEMO_ADMIN_EMAIL=admin@yourdomain.com
NEXT_PUBLIC_DEMO_ADMIN_PASSWORD=...
NEXT_PUBLIC_DEMO_USER_EMAIL=user@yourdomain.com
NEXT_PUBLIC_DEMO_USER_PASSWORD=...
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
