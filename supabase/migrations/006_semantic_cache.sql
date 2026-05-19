-- Semantic response cache.
-- Stores (query_text, embedding, full_LLM_response) per user.
-- The chat route checks this before running the agent; on a hit the LLM is
-- never called. Scoped per user so one tenant's cached answers never leak
-- to another tenant whose documents are completely different.

CREATE TABLE semantic_cache (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID         NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    query_text      TEXT         NOT NULL,
    query_embedding vector(1536) NOT NULL,
    response        TEXT         NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- HNSW for fast ANN cosine lookup across cached queries.
CREATE INDEX idx_semantic_cache_embedding
    ON semantic_cache
    USING hnsw (query_embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Supports the TTL filter in search_semantic_cache.
CREATE INDEX idx_semantic_cache_user_created
    ON semantic_cache(user_id, created_at DESC);

-- Service role has full access; no direct browser access needed.
ALTER TABLE semantic_cache ENABLE ROW LEVEL SECURITY;


-- Returns the single closest cached response for a user if it is within the
-- similarity threshold and has not expired. Uses HNSW for the ANN pass, then
-- filters by threshold so only genuinely similar responses are returned.
CREATE OR REPLACE FUNCTION search_semantic_cache(
    p_user_id            UUID,
    p_query_embedding    vector(1536),
    similarity_threshold float         DEFAULT 0.92,
    max_age_hours        int           DEFAULT 24
)
RETURNS TABLE (id UUID, response TEXT, similarity float)
LANGUAGE sql STABLE AS $$
    SELECT id, response, sim
    FROM (
        SELECT
            sc.id,
            sc.response,
            1 - (p_query_embedding <=> sc.query_embedding) AS sim
        FROM semantic_cache sc
        WHERE
            sc.user_id = p_user_id
            AND sc.created_at > now() - (max_age_hours || ' hours')::INTERVAL
        ORDER BY sc.query_embedding <=> p_query_embedding
        LIMIT 1
    ) nearest
    WHERE sim >= similarity_threshold;
$$;
