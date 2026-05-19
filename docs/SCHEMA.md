# Database Schema — Enterprise Customer Support Agent

All SQL targets Supabase (PostgreSQL 15). Migrations live in `supabase/migrations/`
and are numbered to run in order.

---

## pgvector Setup

```sql
-- migration 001
CREATE EXTENSION IF NOT EXISTS vector;
```

`text-embedding-3-small` (OpenAI) produces **1536-dimensional** embeddings. Every
`embedding` column is typed `vector(1536)`.

---

## Tables

### `documents`

Metadata for each uploaded file. The actual file bytes live in Supabase Storage;
this table tracks what has been ingested into the knowledge base.

```sql
CREATE TABLE documents (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,                    -- original filename, e.g. "pricing_v2.pdf"
    file_path    TEXT NOT NULL,                    -- Supabase Storage path
    file_type    TEXT NOT NULL                     -- "pdf" | "docx" | "txt"
                 CHECK (file_type IN ('pdf', 'docx', 'txt')),
    category     TEXT,                             -- optional tag: "pricing", "api-reference", etc.
    size_bytes   BIGINT NOT NULL DEFAULT 0,
    chunk_count  INTEGER NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_documents_user_id ON documents(user_id);
CREATE INDEX idx_documents_category ON documents(category);
```

---

### `document_chunks`

One row per chunk. Has both a dense vector column (`embedding`) and a sparse full-text
column (`content_tsvector`) to support hybrid search.

```sql
CREATE TABLE document_chunks (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id       UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content           TEXT NOT NULL,
    embedding         vector(1536) NOT NULL,        -- OpenAI text-embedding-3-small output
    content_tsvector  TSVECTOR GENERATED ALWAYS AS  -- auto-maintained BM25 column
                      (to_tsvector('english', content)) STORED,
    page_number       INTEGER,
    chunk_index       INTEGER NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- GIN index: fast full-text keyword search (sparse / BM25 leg of hybrid search).
CREATE INDEX idx_document_chunks_fts ON document_chunks USING gin(content_tsvector);

-- HNSW index: approximate nearest-neighbour cosine search (dense leg).
CREATE INDEX idx_document_chunks_embedding
    ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

**Why `GENERATED ALWAYS AS ... STORED`:** `tsvector` is computed automatically by
Postgres on every insert/update — no application code needed to maintain it.

**Why HNSW over IVFFlat:** better recall for incrementally-growing datasets; no need
to specify cluster count upfront.

---

### `conversations`

One row per chat session. `title` is auto-generated from the first user message
and updated on first agent response.

```sql
CREATE TABLE conversations (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title        TEXT,                             -- null until first message is sent
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_conversations_user_id ON conversations(user_id);

-- Keep updated_at current automatically.
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

---

### `messages`

Every turn in a conversation — both user messages and agent responses.

```sql
CREATE TABLE messages (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id  UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role             TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content          TEXT NOT NULL,
    sources          JSONB,                        -- [{"doc_name": "...", "page_number": 3}, ...]
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);
```

`sources` is JSONB (not a foreign key array) because the chunk metadata is read-only
context for the user — it doesn't need relational integrity enforced at the DB level.

---

### `escalated_tickets`

Created by `escalation_tool` when the agent cannot answer confidently.

```sql
CREATE TABLE escalated_tickets (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id     UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title               TEXT NOT NULL,             -- auto-generated from unanswered question
    linear_ticket_id    TEXT,                      -- Linear issue ID (e.g. "ENG-42")
    linear_ticket_url   TEXT,                      -- full Linear URL
    status              TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open', 'in_progress', 'resolved')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at         TIMESTAMPTZ                -- null until resolved
);

CREATE INDEX idx_escalated_tickets_user_id ON escalated_tickets(user_id);
CREATE INDEX idx_escalated_tickets_status ON escalated_tickets(status);
CREATE INDEX idx_escalated_tickets_created_at ON escalated_tickets(created_at DESC);
```

---

### `knowledge_gaps`

Every question the agent could not answer is logged here so the team can identify
missing documentation. Questions are NOT deduplicated at insert time — the admin
dashboard groups by `question` text and sorts by count.

```sql
CREATE TABLE knowledge_gaps (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id  UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    question         TEXT NOT NULL,                -- the unanswered question verbatim
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_knowledge_gaps_created_at ON knowledge_gaps(created_at DESC);
```

The admin query for frequency:

```sql
SELECT question, COUNT(*) AS frequency, MAX(created_at) AS last_seen
FROM knowledge_gaps
GROUP BY question
ORDER BY frequency DESC, last_seen DESC;
```

---

## Search Functions

Two Postgres functions support the retrieval pipeline. Both are called via
`supabase.rpc()` from the Python `retriever_tool`.

### `hybrid_search_chunks` — used for semantic questions

Combines dense vector search and BM25 keyword search via **Reciprocal Rank Fusion (RRF)**.

```
RRF score = 1/(60 + rank_semantic) + 1/(60 + rank_keyword)
```

Both legs retrieve 20 candidates; RRF merges them into one ranked list. The Python
layer then re-ranks the top results with a cross-encoder before returning to the agent.

```sql
hybrid_search_chunks(
    query_embedding  vector(1536),   -- from OpenAI text-embedding-3-small
    query_text       TEXT,           -- rewritten query string (for BM25 leg)
    match_count      INT DEFAULT 20  -- candidates returned to cross-encoder
)
```

### `exact_search_chunks` — used for exact lookup queries

Pure BM25 (`ts_rank_cd` with cover-density scoring). Used when the query rewriter
classifies the query as `exact_lookup` — e.g. "show me the 403 error section",
"what does clause 4.2 say". No vector math involved; returns verbatim document text.

```sql
exact_search_chunks(
    query_text   TEXT,
    match_count  INT DEFAULT 10
)
```

### Query routing (handled in Python, not SQL)

```
User query
    │
    ▼
Query Rewriter (Claude Haiku)
    │ classifies + rewrites
    ▼
type = "exact_lookup"  ──►  exact_search_chunks()  ──►  return top results (no re-rank)
type = "semantic"      ──►  hybrid_search_chunks()  ──►  cross-encoder re-rank  ──►  top-5
```

---

## Relationships (ERD summary)

```
auth.users
    │
    ├──► documents (user_id)
    │         │
    │         └──► document_chunks (document_id)
    │
    ├──► conversations (user_id)
    │         │
    │         ├──► messages (conversation_id)
    │         ├──► escalated_tickets (conversation_id)
    │         └──► knowledge_gaps (conversation_id)
    │
    └──► escalated_tickets (user_id)
```

All child rows cascade-delete when the parent `auth.users` row is deleted, keeping
the database clean when a user account is removed.

---

## Storage Bucket

Defined in migration 005. The bucket `documents` holds original uploaded files.

```sql
INSERT INTO storage.buckets (id, name, public)
VALUES ('documents', 'documents', false);
```

`public: false` — files are only accessible via signed URLs generated server-side.
The FastAPI backend generates a signed URL when it needs to read a file for ingestion.
