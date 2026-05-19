-- Documents: one row per uploaded file.
-- Original file bytes live in Supabase Storage; this table tracks ingestion metadata.
CREATE TABLE documents (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    file_path    TEXT NOT NULL,
    file_type    TEXT NOT NULL CHECK (file_type IN ('pdf', 'docx', 'txt')),
    category     TEXT,
    size_bytes   BIGINT NOT NULL DEFAULT 0,
    chunk_count  INTEGER NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_documents_user_id   ON documents(user_id);
CREATE INDEX idx_documents_category  ON documents(category);

-- Document chunks: one row per chunk produced by the ingestion pipeline.
-- embedding: 1536-dim output of OpenAI text-embedding-3-small.
-- content_tsvector: pre-computed full-text search vector for BM25 (keyword) search.
CREATE TABLE document_chunks (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id       UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content           TEXT NOT NULL,
    embedding         vector(1536) NOT NULL,
    content_tsvector  TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    page_number       INTEGER,
    chunk_index       INTEGER NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_document_chunks_document_id  ON document_chunks(document_id);

-- GIN index for fast full-text keyword search (the sparse/BM25 leg of hybrid search).
CREATE INDEX idx_document_chunks_fts
    ON document_chunks
    USING gin(content_tsvector);

-- HNSW index for fast approximate nearest-neighbour cosine search (the dense leg).
-- m=16, ef_construction=64 are standard defaults; tune up if recall is insufficient.
CREATE INDEX idx_document_chunks_embedding
    ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ---------------------------------------------------------------------------
-- Hybrid search function (dense + sparse via Reciprocal Rank Fusion).
--
-- How it works:
--   1. Semantic leg: ranks chunks by cosine distance to query_embedding (top 20).
--   2. Keyword leg:  ranks chunks by BM25 (ts_rank_cd) against query_text (top 20).
--   3. RRF merges both ranked lists: score = 1/(60+rank_semantic) + 1/(60+rank_keyword).
--      k=60 is the standard RRF constant — dampens the influence of very high ranks.
--   4. Returns the top match_count chunks by combined RRF score, joined with doc metadata.
--
-- The Python layer then re-ranks these candidates with a cross-encoder before
-- returning the final results to the agent.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION hybrid_search_chunks(
    query_embedding  vector(1536),
    query_text       TEXT,
    match_count      INT DEFAULT 20
)
RETURNS TABLE (
    id           UUID,
    document_id  UUID,
    content      TEXT,
    page_number  INTEGER,
    rrf_score    FLOAT,
    doc_name     TEXT,
    doc_category TEXT
)
LANGUAGE sql STABLE AS $$
    WITH semantic_ranked AS (
        SELECT
            id,
            ROW_NUMBER() OVER (ORDER BY embedding <=> query_embedding) AS rank
        FROM document_chunks
        ORDER BY embedding <=> query_embedding
        LIMIT 20
    ),
    keyword_ranked AS (
        SELECT
            id,
            ROW_NUMBER() OVER (
                ORDER BY ts_rank_cd(content_tsvector, websearch_to_tsquery('english', query_text)) DESC
            ) AS rank
        FROM document_chunks
        WHERE content_tsvector @@ websearch_to_tsquery('english', query_text)
        ORDER BY ts_rank_cd(content_tsvector, websearch_to_tsquery('english', query_text)) DESC
        LIMIT 20
    ),
    rrf AS (
        SELECT
            COALESCE(s.id, k.id) AS id,
            COALESCE(1.0 / (60 + s.rank), 0.0) +
            COALESCE(1.0 / (60 + k.rank), 0.0) AS rrf_score
        FROM semantic_ranked s
        FULL OUTER JOIN keyword_ranked k ON s.id = k.id
    )
    SELECT
        dc.id,
        dc.document_id,
        dc.content,
        dc.page_number,
        rrf.rrf_score,
        d.name     AS doc_name,
        d.category AS doc_category
    FROM rrf
    JOIN document_chunks dc ON dc.id = rrf.id
    JOIN documents        d  ON d.id  = dc.document_id
    ORDER BY rrf.rrf_score DESC
    LIMIT match_count;
$$;

-- ---------------------------------------------------------------------------
-- Exact match search function (keyword-only, no vector search).
-- Used when query rewriter classifies the query as exact_lookup
-- (e.g. "show me the text about error 403", "what does section 4.2 say").
-- ts_rank_cd scores by cover density — better for short exact phrases.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION exact_search_chunks(
    query_text   TEXT,
    match_count  INT DEFAULT 10
)
RETURNS TABLE (
    id           UUID,
    document_id  UUID,
    content      TEXT,
    page_number  INTEGER,
    bm25_score   FLOAT,
    doc_name     TEXT,
    doc_category TEXT
)
LANGUAGE sql STABLE AS $$
    SELECT
        dc.id,
        dc.document_id,
        dc.content,
        dc.page_number,
        ts_rank_cd(dc.content_tsvector, websearch_to_tsquery('english', query_text))::FLOAT AS bm25_score,
        d.name     AS doc_name,
        d.category AS doc_category
    FROM document_chunks dc
    JOIN documents d ON d.id = dc.document_id
    WHERE dc.content_tsvector @@ websearch_to_tsquery('english', query_text)
    ORDER BY bm25_score DESC
    LIMIT match_count;
$$;
