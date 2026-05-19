-- ---------------------------------------------------------------------------
-- Storage bucket for uploaded documents.
-- Original files are stored here for audit trail — not used in retrieval.
-- public: false means files are only accessible via signed URLs.
-- ---------------------------------------------------------------------------
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'documents',
    'documents',
    false,
    52428800,   -- 50 MB per file
    ARRAY['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain']
);

-- ---------------------------------------------------------------------------
-- Storage RLS policies
-- Users can upload to their own folder: documents/{user_id}/filename
-- Users can only read files they uploaded.
-- ---------------------------------------------------------------------------
CREATE POLICY "users can upload own documents"
    ON storage.objects FOR INSERT
    TO authenticated
    WITH CHECK (
        bucket_id = 'documents'
        AND (storage.foldername(name))[1] = auth.uid()::text
    );

CREATE POLICY "users can read own documents"
    ON storage.objects FOR SELECT
    TO authenticated
    USING (
        bucket_id = 'documents'
        AND (storage.foldername(name))[1] = auth.uid()::text
    );

CREATE POLICY "users can delete own documents"
    ON storage.objects FOR DELETE
    TO authenticated
    USING (
        bucket_id = 'documents'
        AND (storage.foldername(name))[1] = auth.uid()::text
    );
