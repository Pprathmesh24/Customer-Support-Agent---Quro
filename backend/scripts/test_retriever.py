"""
End-to-end test of RetrieverTool.
Ingests a real document, then tests semantic and exact_lookup query paths.
Requires OPENAI_API_KEY and ANTHROPIC_API_KEY to be set in .env.
Usage: uv run scripts/test_retriever.py
"""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from langchain_anthropic import ChatAnthropic
from openai import AsyncOpenAI
from supabase import create_client

from app.agent.tools.retriever import RetrieverTool
from app.core.settings import settings
from app.ingestion.pipeline import ingest

TEST_EMAIL = "test-retriever@example.com"
TEST_PASSWORD = "test-retriever-pw-2222"

# Document content with a mix of semantic and verbatim-queryable sections
DOCUMENT = """
Authentication Guide

Overview
The API uses Bearer token authentication. Every request must include an
Authorization header with a valid JWT token issued by the authentication service.

Error Codes
- ERROR_401: Token is missing or malformed.
- ERROR_403: Token is valid but the user lacks permission for the requested resource.
- ERROR_429: Rate limit exceeded. Maximum 100 requests per minute per API key.

Getting a Token
To obtain a token, send a POST request to /auth/token with your client_id and
client_secret in the request body. Tokens expire after 3600 seconds (1 hour).
Use the refresh_token field in the response to obtain a new token without
re-entering credentials.

Rate Limiting
The API enforces rate limits to ensure fair usage. If you exceed the limit you
will receive an ERROR_429 response. Implement exponential backoff in your client:
start with a 1-second delay and double it on each retry up to a maximum of 32 seconds.

Permissions
Permissions are role-based. Available roles are: viewer, editor, and admin.
Viewers can read all resources. Editors can create and update. Admins have full access
including deletion and user management.
""".strip()


async def main() -> None:
    for key, name in [(settings.openai_api_key, "OPENAI_API_KEY"),
                      (settings.anthropic_api_key, "ANTHROPIC_API_KEY")]:
        if not key:
            print(f"ERROR: {name} is not set in .env")
            sys.exit(1)

    service = create_client(settings.supabase_url, settings.supabase_service_role_key)
    user_resp = service.auth.admin.create_user(
        {"email": TEST_EMAIL, "password": TEST_PASSWORD, "email_confirm": True}
    )
    user_id: str = user_resp.user.id
    print(f"Temp user: {user_id}")

    document_id: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            tmp = Path(f.name)
            tmp.write_text(DOCUMENT, encoding="utf-8")

        print("Ingesting test document...")
        document_id = await ingest(tmp, user_id, service, category="API Docs")
        doc = service.table("documents").select("chunk_count").eq("id", document_id).execute()
        print(f"Ingested {doc.data[0]['chunk_count']} chunks\n")

        tool = RetrieverTool(
            supabase=service,
            llm=ChatAnthropic(
                model=settings.llm_model,
                api_key=settings.anthropic_api_key,
            ),
            openai_client=AsyncOpenAI(api_key=settings.openai_api_key),
        )

        # ── Test 1: semantic query ────────────────────────────────────────────
        print("=" * 60)
        print("TEST 1 — Semantic query: 'How does token refresh work?'")
        print("=" * 60)
        result1 = await tool._arun("How does token refresh work?")
        print(result1)
        assert "refresh" in result1.lower() or "token" in result1.lower(), \
            "Expected token/refresh content in semantic result"

        # ── Test 2: exact lookup ─────────────────────────────────────────────
        print("=" * 60)
        print("TEST 2 — Exact lookup: 'ERROR_403'")
        print("=" * 60)
        result2 = await tool._arun("ERROR_403")
        print(result2)
        assert "ERROR_403" in result2 or "403" in result2, \
            "Expected ERROR_403 in exact lookup result"

        print("\nRetrieverTool OK")

    finally:
        if document_id:
            service.table("documents").delete().eq("id", document_id).execute()
        service.auth.admin.delete_user(user_id)
        tmp.unlink(missing_ok=True)
        print("Cleanup done")


if __name__ == "__main__":
    asyncio.run(main())
