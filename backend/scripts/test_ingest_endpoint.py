"""
End-to-end test of POST /ingest.
Runs the FastAPI app in-process (no server needed), creates a real Supabase auth
user, signs in to get a JWT, posts a sample TXT file, and verifies the response.
Usage: uv run scripts/test_ingest_endpoint.py
"""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import httpx
from supabase import create_client

from app.core.settings import settings
from app.main import app

TEST_EMAIL = "test-ingest-endpoint@example.com"
TEST_PASSWORD = "test-ingest-endpoint-pw-3456"

SAMPLE = (
    "Hybrid Search Guide\n\n"
    "This document explains how hybrid search works in the Enterprise Customer "
    "Support Agent. Dense vector search uses HNSW cosine similarity. Sparse BM25 "
    "search uses Postgres tsvector. Both results are merged via Reciprocal Rank Fusion.\n\n"
    "The cross-encoder re-ranker then re-scores the top 20 candidates and returns "
    "the top 5 most relevant chunks to the LangGraph ReAct agent."
)


async def main() -> None:
    if not settings.openai_api_key:
        print("ERROR: OPENAI_API_KEY is not set in .env")
        sys.exit(1)

    service = create_client(settings.supabase_url, settings.supabase_service_role_key)

    # Create and sign in as a test user to get a real JWT
    service.auth.admin.create_user(
        {"email": TEST_EMAIL, "password": TEST_PASSWORD, "email_confirm": True}
    )
    anon = create_client(settings.supabase_url, settings.supabase_anon_key)
    session = anon.auth.sign_in_with_password({"email": TEST_EMAIL, "password": TEST_PASSWORD})
    token: str = session.session.access_token
    user_id: str = session.user.id
    print(f"Signed in as: {user_id}")

    document_id: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            tmp = Path(f.name)
            tmp.write_text(SAMPLE, encoding="utf-8")

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Health check
            health = await client.get("/health")
            assert health.status_code == 200, f"Health check failed: {health.text}"
            print(f"Health: {health.json()}")

            # POST /ingest
            with tmp.open("rb") as fh:
                resp = await client.post(
                    "/ingest",
                    headers={"Authorization": f"Bearer {token}"},
                    files={"file": ("sample.txt", fh, "text/plain")},
                    data={"category": "test"},
                    timeout=120,
                )

        assert resp.status_code == 200, f"Unexpected status {resp.status_code}: {resp.text}"
        body = resp.json()
        document_id = body["document_id"]
        print(f"Response: document_id={document_id}, chunk_count={body['chunk_count']}")
        assert body["chunk_count"] > 0, "chunk_count is 0"

        # Verify chunks exist in Supabase
        chunks = (
            service.table("document_chunks")
            .select("id", count="exact")
            .eq("document_id", document_id)
            .execute()
        )
        print(f"Chunks in Supabase: {chunks.count}")
        assert chunks.count == body["chunk_count"], "Chunk count mismatch"

        print("\nIngest endpoint OK")

    finally:
        if document_id:
            service.table("documents").delete().eq("id", document_id).execute()
        service.auth.admin.delete_user(user_id)
        tmp.unlink(missing_ok=True)
        print("Cleanup done")


if __name__ == "__main__":
    asyncio.run(main())
