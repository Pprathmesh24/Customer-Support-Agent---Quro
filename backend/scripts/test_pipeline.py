"""
End-to-end ingestion pipeline test.
Creates a temp TXT file, ingests it, verifies chunks in Supabase, then cleans up.
Usage: uv run scripts/test_pipeline.py
"""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from supabase import create_client

from app.core.settings import settings
from app.ingestion.pipeline import ingest

TEST_EMAIL = "test-pipeline@example.com"
TEST_PASSWORD = "test-pipeline-pw-9012"

SAMPLE_CONTENT = "\n\n".join([
    "Introduction to Hybrid Search",
    "Hybrid search combines two retrieval strategies: dense vector search using "
    "HNSW cosine similarity and sparse BM25 keyword search using Postgres tsvector. "
    "The two ranked lists are merged using Reciprocal Rank Fusion with k=60.",
    "Re-ranking",
    "After hybrid search returns the top 20 candidates, a cross-encoder model "
    "(ms-marco-MiniLM-L-6-v2) re-scores each pair of (query, chunk) and selects "
    "the top 5 most relevant results. This runs locally with no API cost.",
    "Query Rewriting",
    "Before embedding, Claude Haiku rewrites the user query to expand acronyms, "
    "add domain context, and clarify ambiguous intent. This improves the quality "
    "of the dense retrieval leg significantly.",
    "Query Routing",
    "Claude Haiku also classifies each query as exact_lookup or semantic. "
    "Exact lookups skip vector search entirely and use BM25 only — ideal for "
    "verbatim phrases like error codes or section references.",
] * 3)


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
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            tmp_path = Path(f.name)
            tmp_path.write_text(SAMPLE_CONTENT, encoding="utf-8")

        print(f"Ingesting {tmp_path.name} ({tmp_path.stat().st_size} bytes)...")
        document_id = await ingest(tmp_path, user_id, supabase, category="test")
        print(f"Document ID: {document_id}")

        # Verify document row
        doc = supabase.table("documents").select("*").eq("id", document_id).execute()
        row = doc.data[0]
        print(f"Document row: name={row['name']!r}, file_type={row['file_type']!r}, "
              f"chunk_count={row['chunk_count']}, size_bytes={row['size_bytes']}")
        assert row["chunk_count"] > 0, "chunk_count was not updated"

        # Verify chunks
        chunks = (
            supabase.table("document_chunks")
            .select("id, chunk_index, page_number, embedding")
            .eq("document_id", document_id)
            .order("chunk_index")
            .execute()
        )
        print(f"Chunks in Supabase: {len(chunks.data)}")
        assert len(chunks.data) == row["chunk_count"], "Chunk count mismatch"
        for chunk in chunks.data:
            assert chunk["embedding"] is not None, f"Null embedding on chunk {chunk['chunk_index']}"
        print("All embeddings: non-null ✓")
        print("Foreign keys:   document_id matches ✓")

        print("\nPipeline OK")

    finally:
        if document_id:
            supabase.table("documents").delete().eq("id", document_id).execute()
        supabase.auth.admin.delete_user(user_id)
        tmp_path.unlink(missing_ok=True)
        print("Cleanup done")


if __name__ == "__main__":
    asyncio.run(main())
