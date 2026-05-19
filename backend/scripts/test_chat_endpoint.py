"""
Integration test for POST /chat.
Ingests a fixture doc, then calls the endpoint twice:
  - First call: cold path (agent runs, cache populated)
  - Second call: identical question (cache hit)
Usage: uv run scripts/test_chat_endpoint.py
"""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import httpx
from openai import AsyncOpenAI
from supabase import create_client

from app.core.settings import settings
from app.ingestion.pipeline import ingest
from app.main import app

TEST_EMAIL = "test-chat-ep@example.com"
TEST_PASSWORD = "test-chat-ep-pw-9999"

_FIXTURE_DOC = """\
# Quro Help Center

## How to Reset Your Password
To reset your password:
1. Go to the login page and click "Forgot password".
2. Enter your registered email address.
3. Check your inbox for a reset link (valid for 24 hours).
4. Click the link and choose a new password.

## Password Requirements
Your password must:
- Be at least 8 characters long
- Contain at least one uppercase letter (A–Z)
- Contain at least one digit (0–9)
- Contain at least one special character (!, @, #, $)
- Not match any of your last 5 passwords
"""


async def main() -> None:
    service = create_client(settings.supabase_url, settings.supabase_service_role_key)
    anon = create_client(settings.supabase_url, settings.supabase_anon_key)

    # ── Setup ─────────────────────────────────────────────────────────────────
    user_resp = service.auth.admin.create_user(
        {"email": TEST_EMAIL, "password": TEST_PASSWORD, "email_confirm": True}
    )
    user_id: str = user_resp.user.id
    print(f"Temp user: {user_id}")

    session = anon.auth.sign_in_with_password(
        {"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    token: str = session.session.access_token
    headers = {"Authorization": f"Bearer {token}"}

    conv = (
        service.table("conversations")
        .insert({"user_id": user_id, "title": "Chat endpoint test"})
        .execute()
    )
    conversation_id: str = conv.data[0]["id"]
    print(f"Conversation: {conversation_id}")

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
        f.write(_FIXTURE_DOC)
        fixture_path = Path(f.name)

    document_id: str | None = None

    try:
        openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        document_id = await ingest(
            file_path=fixture_path,
            user_id=user_id,
            supabase=service,
            category="help-center",
        )
        fixture_path.unlink()
        print(f"Document ingested: {document_id}")

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # ── Cold call (agent runs, response cached) ───────────────────────
            print("\n── Cold call ────────────────────────────────────────────")
            resp = await client.post(
                "/chat",
                json={"message": "How do I reset my password?", "conversation_id": conversation_id},
                headers=headers,
                timeout=120.0,
            )
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
            body = resp.json()
            print(f"Answer: {body['answer'][:200]}...")
            print(f"Sources: {body['sources']}")
            print(f"Cached: {body['cached']}")

            assert body["answer"], "Answer must not be empty"
            assert body["cached"] is False, "First call must not be cached"
            assert body["sources"], "Expected at least one source citation"
            print("[✓] Cold call passed — answer with sources returned")

            # ── Warm call (identical question → cache hit) ────────────────────
            print("\n── Warm call (cache hit) ─────────────────────────────────")
            resp2 = await client.post(
                "/chat",
                json={"message": "How do I reset my password?", "conversation_id": conversation_id},
                headers=headers,
                timeout=30.0,
            )
            assert resp2.status_code == 200, f"Expected 200, got {resp2.status_code}: {resp2.text}"
            body2 = resp2.json()
            print(f"Answer: {body2['answer'][:200]}...")
            print(f"Cached: {body2['cached']}")

            assert body2["cached"] is True, "Second identical call must be a cache hit"
            print("[✓] Warm call passed — cache hit confirmed")

            # ── 404 for wrong conversation ────────────────────────────────────
            print("\n── 404 guard ─────────────────────────────────────────────")
            resp3 = await client.post(
                "/chat",
                json={"message": "test", "conversation_id": "00000000-0000-0000-0000-000000000000"},
                headers=headers,
                timeout=10.0,
            )
            assert resp3.status_code == 404, f"Expected 404, got {resp3.status_code}"
            print("[✓] 404 returned for unknown conversation")

        print(f"\n{'=' * 60}")
        print("POST /chat OK")

    finally:
        service.table("semantic_cache").delete().eq("user_id", user_id).execute()
        service.table("escalated_tickets").delete().eq("conversation_id", conversation_id).execute()
        service.table("knowledge_gaps").delete().eq("conversation_id", conversation_id).execute()
        service.table("conversations").delete().eq("id", conversation_id).execute()
        if document_id:
            service.table("document_chunks").delete().eq("document_id", document_id).execute()
            service.table("documents").delete().eq("id", document_id).execute()
        service.auth.admin.delete_user(user_id)
        print("Cleanup done")


if __name__ == "__main__":
    asyncio.run(main())
