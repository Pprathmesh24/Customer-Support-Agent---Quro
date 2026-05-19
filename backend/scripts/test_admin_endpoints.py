"""
Tests admin endpoints (Step 6.3):
  1. GET /admin/escalations  — returns tickets, filters by status
  2. GET /admin/knowledge-gaps — returns questions grouped by frequency
  3. Unhandled exception → structured JSON 500 body (not raw traceback)
Usage: uv run scripts/test_admin_endpoints.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import httpx
from fastapi import APIRouter
from supabase import create_client

from app.core.settings import settings
from app.main import app

TEST_EMAIL = "test-admin-ep@example.com"
TEST_PASSWORD = "test-admin-ep-pw-2020"


async def main() -> None:
    service = create_client(settings.supabase_url, settings.supabase_service_role_key)
    anon = create_client(settings.supabase_url, settings.supabase_anon_key)

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
        .insert({"user_id": user_id, "title": "Admin test conv"})
        .execute()
    )
    conversation_id: str = conv.data[0]["id"]

    ticket_ids: list[str] = []
    gap_ids: list[str] = []

    try:
        # ── Seed test data ────────────────────────────────────────────────────
        for i, status in enumerate(["open", "open", "in_progress"]):
            t = (
                service.table("escalated_tickets")
                .insert({
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "title": f"Test ticket {i}",
                    "status": status,
                })
                .execute()
            )
            ticket_ids.append(t.data[0]["id"])

        for question in ["How do I reset my password?", "How do I reset my password?", "Where is my invoice?"]:
            g = (
                service.table("knowledge_gaps")
                .insert({"conversation_id": conversation_id, "question": question})
                .execute()
            )
            gap_ids.append(g.data[0]["id"])

        # ── Add deliberate-error route only for this test process ─────────────
        _test_router = APIRouter()

        @_test_router.get("/__test_error__")
        async def _trigger_error() -> None:
            raise RuntimeError("deliberate test error")

        app.include_router(_test_router)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:

            # ── 1. GET /admin/escalations (all) ───────────────────────────────
            print("\n── GET /admin/escalations ────────────────────────────────")
            r1 = await client.get("/admin/escalations", headers=headers)
            assert r1.status_code == 200, f"{r1.status_code}: {r1.text}"
            data1 = r1.json()
            assert data1["total"] >= 3
            print(f"Total escalations: {data1['total']} | Returned: {len(data1['items'])}")
            assert all("title" in item for item in data1["items"])
            print("[✓] GET /admin/escalations OK")

            # ── 2. Status filter ──────────────────────────────────────────────
            print("\n── GET /admin/escalations?status=open ────────────────────")
            r2 = await client.get("/admin/escalations?status=open", headers=headers)
            assert r2.status_code == 200, f"{r2.status_code}: {r2.text}"
            data2 = r2.json()
            assert all(item["status"] == "open" for item in data2["items"])
            print(f"Open tickets: {data2['total']}")
            print("[✓] Status filter OK")

            # ── 3. GET /admin/knowledge-gaps ──────────────────────────────────
            print("\n── GET /admin/knowledge-gaps ─────────────────────────────")
            r3 = await client.get("/admin/knowledge-gaps", headers=headers)
            assert r3.status_code == 200, f"{r3.status_code}: {r3.text}"
            data3 = r3.json()
            assert data3["total"] >= 2
            items = data3["items"]
            # "How do I reset my password?" appears twice — should be first
            assert items[0]["question"] == "How do I reset my password?"
            assert items[0]["count"] >= 2
            print(f"Distinct questions: {data3['total']}")
            for item in items[:3]:
                print(f"  [{item['count']}x] {item['question'][:60]}")
            print("[✓] GET /admin/knowledge-gaps OK (frequency-sorted)")

            # ── 4. Deliberate 500 → structured JSON body ──────────────────────
            # Starlette's ServerErrorMiddleware always re-raises the exception after
            # sending the response (so production servers can log it), which makes
            # httpx propagate it rather than return the response. We verify the handler
            # directly via app.exception_handlers instead.
            print("\n── Deliberate 500 error handler ──────────────────────────")
            import json as _json
            from fastapi import Request as _Request
            _handler = app.exception_handlers.get(Exception)
            assert _handler is not None, "Exception handler not registered on app"
            _scope = {"type": "http", "method": "GET", "path": "/", "query_string": b"", "headers": []}
            _response = await _handler(_Request(_scope), RuntimeError("deliberate test error"))
            assert _response.status_code == 500, f"Expected 500, got {_response.status_code}"
            _body = _json.loads(_response.body)
            assert _body.get("error") == "internal_server_error", f"Unexpected body: {_body}"
            assert "detail" in _body
            print(f"Error body: {_body}")
            print("[✓] Structured JSON 500 OK")

            # ── 5. Auth guard ─────────────────────────────────────────────────
            print("\n── Auth guard ────────────────────────────────────────────")
            r5 = await client.get("/admin/escalations")
            assert r5.status_code == 422  # missing Authorization header → 422 from FastAPI
            print("[✓] Auth guard OK")

        print(f"\n{'=' * 60}")
        print("Admin endpoints OK")

    finally:
        for gap_id in gap_ids:
            service.table("knowledge_gaps").delete().eq("id", gap_id).execute()
        for tid in ticket_ids:
            service.table("escalated_tickets").delete().eq("id", tid).execute()
        service.table("conversations").delete().eq("id", conversation_id).execute()
        service.auth.admin.delete_user(user_id)
        print("Cleanup done")


if __name__ == "__main__":
    asyncio.run(main())
