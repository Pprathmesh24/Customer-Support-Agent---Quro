-- ---------------------------------------------------------------------------
-- Enable RLS on all tables.
-- Without this, policies exist but are not enforced.
-- The service_role key bypasses RLS entirely — only use it server-side.
-- ---------------------------------------------------------------------------
ALTER TABLE documents          ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks    ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations      ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages           ENABLE ROW LEVEL SECURITY;
ALTER TABLE escalated_tickets  ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_gaps     ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- documents
-- Users can only see and manage their own uploaded documents.
-- ---------------------------------------------------------------------------
CREATE POLICY "users can view own documents"
    ON documents FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "users can insert own documents"
    ON documents FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "users can delete own documents"
    ON documents FOR DELETE
    USING (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- document_chunks
-- Chunks are readable by any authenticated user — the knowledge base is
-- shared across all users of the same deployment.
-- Write access is service_role only (FastAPI ingest pipeline).
-- ---------------------------------------------------------------------------
CREATE POLICY "authenticated users can read chunks"
    ON document_chunks FOR SELECT
    TO authenticated
    USING (true);

-- ---------------------------------------------------------------------------
-- conversations
-- Users can only see and manage their own conversations.
-- ---------------------------------------------------------------------------
CREATE POLICY "users can view own conversations"
    ON conversations FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "users can insert own conversations"
    ON conversations FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "users can update own conversations"
    ON conversations FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "users can delete own conversations"
    ON conversations FOR DELETE
    USING (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- messages
-- Users can read and write messages in conversations they own.
-- Join through conversations to verify ownership.
-- ---------------------------------------------------------------------------
CREATE POLICY "users can view messages in own conversations"
    ON messages FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM conversations c
            WHERE c.id = messages.conversation_id
              AND c.user_id = auth.uid()
        )
    );

CREATE POLICY "users can insert messages in own conversations"
    ON messages FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM conversations c
            WHERE c.id = messages.conversation_id
              AND c.user_id = auth.uid()
        )
    );

-- ---------------------------------------------------------------------------
-- escalated_tickets
-- Users can view their own tickets. Only service_role can insert/update
-- (escalation_tool runs server-side with the service key).
-- ---------------------------------------------------------------------------
CREATE POLICY "users can view own escalated tickets"
    ON escalated_tickets FOR SELECT
    USING (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- knowledge_gaps
-- Readable and writable only via service_role (server-side only).
-- Regular users have no direct access.
-- ---------------------------------------------------------------------------
-- No policies needed — RLS is enabled with no permissive policies,
-- which means all access is denied for non-service_role callers.
