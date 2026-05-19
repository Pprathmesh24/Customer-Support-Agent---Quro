"""
Tests the embedder: embeds chunks from sample text and stores them in Supabase.
Verifies each row has a non-null embedding, then cleans up.
Usage: uv run scripts/test_embedder.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from supabase import create_client

from app.core.settings import settings
from app.ingestion.chunker import chunk_text
from app.ingestion.embedder import embed_and_store

TEST_EMAIL = "test-embedder@example.com"
TEST_PASSWORD = "test-embedder-pw-5678"

SAMPLE = (
    "Enterprise Customer Support Agent uses hybrid search combining dense vector "
    "similarity with sparse BM25 keyword retrieval. Results are merged via "
    "Reciprocal Rank Fusion and re-ranked by a cross-encoder before being "
    "presented to the LangGraph ReAct agent. The system supports PDF, DOCX, and "
    "plain text uploads. Documents are chunked into 800-character segments with "
    "100-character overlap to preserve sentence context across boundaries."
)


async def main() -> None:
    if not settings.openai_api_key:
        print("ERROR: OPENAI_API_KEY is not set in .env")
        sys.exit(1)

    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)

    user_resp = supabase.auth.admin.create_user(
        {"email": TEST_EMAIL, "password": TEST_PASSWORD, "email_confirm": True}
    )
    user_id: str = user_resp.user.id
    print(f"Temp user: {user_id}")

    document_id: str | None = None
    try:
        doc = (
            supabase.table("documents")
            .insert({
                "user_id": user_id,
                "name": "test-embedder-document",
                "file_path": "test/test-doc.txt",
                "file_type": "txt",
            })
            .execute()
        )
        document_id = doc.data[0]["id"]
        print(f"Document row: {document_id}")

        chunks = chunk_text(SAMPLE)
        print(f"Chunks to embed: {len(chunks)}")

        stored = await embed_and_store(chunks, document_id, supabase)
        print(f"Chunks stored:   {stored}")

        rows = (
            supabase.table("document_chunks")
            .select("id, chunk_index, embedding")
            .eq("document_id", document_id)
            .execute()
        )
        assert len(rows.data) == stored, "Row count mismatch"
        for row in rows.data:
            assert row["embedding"] is not None, f"Null embedding on chunk {row['chunk_index']}"
            print(f"  chunk {row['chunk_index']}: embedding OK ({len(row['embedding'])} chars)")

        print("\nEmbedder OK")

    finally:
        if document_id:
            # ON DELETE CASCADE removes document_chunks automatically
            supabase.table("documents").delete().eq("id", document_id).execute()
        supabase.auth.admin.delete_user(user_id)
        print("Cleanup done")


if __name__ == "__main__":
    asyncio.run(main())
