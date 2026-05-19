-- ---------------------------------------------------------------------------
-- Conversations: one row per chat session.
-- title is null until the first agent response — set from the first user message.
-- ---------------------------------------------------------------------------
CREATE TABLE conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_conversations_user_id    ON conversations(user_id);
CREATE INDEX idx_conversations_updated_at ON conversations(updated_at DESC);

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

-- ---------------------------------------------------------------------------
-- Messages: every turn in a conversation (both user and assistant).
-- sources: JSONB array of { doc_name, page_number } citations attached to
--          assistant messages. Stored as JSONB because it is display-only data
--          and does not need relational integrity.
-- ---------------------------------------------------------------------------
CREATE TABLE messages (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id  UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role             TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content          TEXT NOT NULL,
    sources          JSONB,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_messages_created_at      ON messages(created_at);

-- ---------------------------------------------------------------------------
-- Escalated tickets: created by escalation_tool when the agent cannot answer.
-- linear_ticket_id / linear_ticket_url are populated after Linear API call.
-- resolved_at is null until a support agent marks the ticket resolved.
-- ---------------------------------------------------------------------------
CREATE TABLE escalated_tickets (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id   UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id           UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title             TEXT NOT NULL,
    linear_ticket_id  TEXT,
    linear_ticket_url TEXT,
    status            TEXT NOT NULL DEFAULT 'open'
                      CHECK (status IN ('open', 'in_progress', 'resolved')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at       TIMESTAMPTZ
);

CREATE INDEX idx_escalated_tickets_user_id    ON escalated_tickets(user_id);
CREATE INDEX idx_escalated_tickets_status     ON escalated_tickets(status);
CREATE INDEX idx_escalated_tickets_created_at ON escalated_tickets(created_at DESC);

-- ---------------------------------------------------------------------------
-- Knowledge gaps: every question the agent could not answer is logged here.
-- Not deduplicated at insert time — frequency is computed at query time with
-- GROUP BY so the insert path stays simple and fast.
-- ---------------------------------------------------------------------------
CREATE TABLE knowledge_gaps (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id  UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    question         TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_knowledge_gaps_created_at ON knowledge_gaps(created_at DESC);
