-- ---------------------------------------------------------------------------
-- Admin helper functions for the dashboard endpoints.
-- ---------------------------------------------------------------------------

-- Returns knowledge gaps grouped by question text, sorted by frequency desc.
-- Called by GET /admin/knowledge-gaps with server-side pagination.
CREATE OR REPLACE FUNCTION get_knowledge_gap_summary(p_limit INT, p_offset INT)
RETURNS TABLE (
    question  TEXT,
    count     BIGINT,
    last_seen TIMESTAMPTZ
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        question,
        COUNT(*)::BIGINT  AS count,
        MAX(created_at)   AS last_seen
    FROM  knowledge_gaps
    GROUP BY question
    ORDER BY count DESC, last_seen DESC
    LIMIT  p_limit
    OFFSET p_offset;
$$;

-- Returns the total number of distinct questions in knowledge_gaps.
-- Used for pagination metadata in GET /admin/knowledge-gaps.
CREATE OR REPLACE FUNCTION get_knowledge_gap_count()
RETURNS BIGINT
LANGUAGE sql
STABLE
AS $$
    SELECT COUNT(DISTINCT question) FROM knowledge_gaps;
$$;
