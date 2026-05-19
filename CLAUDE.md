# Enterprise Customer Support Agent

Agentic RAG system: companies upload product docs, customers ask support questions via a
LangGraph ReAct agent backed by a Supabase pgvector knowledge base.

## Stack at a Glance

| Layer              | Technology                                          |
|--------------------|-----------------------------------------------------|
| Frontend           | Next.js 14, TypeScript (strict), Tailwind CSS       |
| Backend            | FastAPI (Python 3.12)                               |
| Agent              | LangGraph ReAct loop, Claude via langchain_anthropic|
| LLM                | claude-haiku-4-5-20251001                           |
| Embeddings         | all-mpnet-base-v2 (HuggingFace, runs locally)       |
| Vector Store       | Supabase pgvector                                   |
| Database           | Supabase PostgreSQL                                 |
| Auth               | Supabase Auth (JWT)                                 |
| Storage            | Supabase Storage                                    |
| Python pkg manager | uv — never use pip install directly                 |

## Rules — Read Every Session

1. **Phase-by-phase only.** Never combine two steps. Stop after every step and wait for explicit approval.
2. **Update `docs/PROGRESS.md`** immediately after every step completes.
3. **Read `docs/PROGRESS.md` first** after any context loss (e.g., after /compact).
4. **Ask before deciding** anything architectural not already specified.
5. **No unnecessary comments** — only comment when WHY is non-obvious.
6. **Never simplify** to make implementation easier. Use idiomatic, production-grade patterns.
7. **Python deps:** always `uv add <package>`. Never `pip install`.

## File Pointers

- Current progress  → `docs/PROGRESS.md`
- Full phase/step plan → `docs/PLAN.md`
- System architecture → `docs/ARCHITECTURE.md`
- Database schema → `docs/SCHEMA.md`

## Code Style

### Python
- Type hints on every function signature (parameters + return type)
- Pydantic models for all request/response shapes
- No bare `except:` — always catch specific exceptions
- Async throughout FastAPI routes and LangGraph nodes

### TypeScript
- `strict: true` in tsconfig — no exceptions
- No `any` types
- Explicit return types on all functions
- Named exports preferred over default exports for components
