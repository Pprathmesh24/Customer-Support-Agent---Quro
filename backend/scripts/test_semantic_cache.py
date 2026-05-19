"""
Test SemanticCache: store a response, verify semantically similar queries hit the
cache and an unrelated query misses. No documents are ingested — the cache is
tested independently of the retrieval pipeline.
Usage: uv run scripts/test_semantic_cache.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from openai import AsyncOpenAI
from supabase import create_client

from app.agent.cache import SemanticCache
from app.core.settings import settings

TEST_EMAIL = "test-cache@example.com"
TEST_PASSWORD = "test-cache-pw-4444"

STORED_QUERY = "How do I cancel my subscription?"
STORED_RESPONSE = (
    "To cancel your subscription, go to Account Settings → Billing → Cancel Plan. "
    "Your access continues until the end of the current billing period. "
    "You won't be charged again after cancellation."
)

# All semantically equivalent to STORED_QUERY — should HIT the cache.
SIMILAR_QUERIES = [
    "I want to unsubscribe",
    "how do I stop being charged",
    "cancel my plan",
    "I don't want to renew my subscription",
]

# Unrelated topic — must MISS.
UNRELATED_QUERY = "What file formats can I upload to the knowledge base?"


async def main() -> None:
    if not settings.openai_api_key:
        print("ERROR: OPENAI_API_KEY not set in .env")
        sys.exit(1)

    service = create_client(settings.supabase_url, settings.supabase_service_role_key)
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

    user_resp = service.auth.admin.create_user(
        {"email": TEST_EMAIL, "password": TEST_PASSWORD, "email_confirm": True}
    )
    user_id: str = user_resp.user.id
    print(f"Temp user: {user_id}")

    try:
        cache = SemanticCache(
            supabase=service,
            openai_client=openai_client,
            similarity_threshold=0.45,
            ttl_hours=1,
        )

        # ── Store ────────────────────────────────────────────────────────────
        print(f"\nStoring: {STORED_QUERY!r}")
        await cache.store(STORED_QUERY, STORED_RESPONSE, user_id)

        # ── Debug: show raw similarity scores to calibrate threshold ────────
        print("\n── Raw similarity scores (threshold=0.0) ────────────────────")
        from app.agent.cache import _embed as _cache_embed
        all_queries = SIMILAR_QUERIES + [UNRELATED_QUERY]
        for query in all_queries:
            emb = await _cache_embed(query, openai_client)
            r = service.rpc("search_semantic_cache", {
                "p_user_id": user_id,
                "p_query_embedding": emb,
                "similarity_threshold": 0.0,
                "max_age_hours": 1,
            }).execute()
            sim = f"{r.data[0]['similarity']:.4f}" if r.data else "no match"
            print(f"  {sim}  {query!r}")

        # ── Similar queries — expect HIT ─────────────────────────────────────
        print("\n── Similar queries (expect CACHE HIT) ───────────────────────")
        for query in SIMILAR_QUERIES:
            result = await cache.check(query, user_id)
            preview = (result[:70] + "...") if result and len(result) > 70 else result
            print(f"  Q: {query!r}")
            print(f"  A: {preview}")
            assert result is not None, f"Expected HIT for: {query!r}"
            print()

        # ── Unrelated query — expect MISS ────────────────────────────────────
        print("── Unrelated query (expect CACHE MISS) ──────────────────────")
        result = await cache.check(UNRELATED_QUERY, user_id)
        print(f"  Q: {UNRELATED_QUERY!r}")
        print(f"  A: {result}")
        assert result is None, f"Expected MISS for: {UNRELATED_QUERY!r}"

        # ── Cross-user isolation — different user must MISS ──────────────────
        print("\n── Cross-user isolation (different user must MISS) ──────────")
        other_user_resp = service.auth.admin.create_user(
            {"email": "test-cache-other@example.com", "password": "test-cache-other-4445", "email_confirm": True}
        )
        other_user_id: str = other_user_resp.user.id
        try:
            result = await cache.check(STORED_QUERY, other_user_id)
            print(f"  Q: {STORED_QUERY!r} (as other user)")
            print(f"  A: {result}")
            assert result is None, "Cross-user cache leak detected!"
            print("  [✓] Other user correctly got a MISS")
        finally:
            service.auth.admin.delete_user(other_user_id)

        print("\nSemanticCache OK")

    finally:
        service.table("semantic_cache").delete().eq("user_id", user_id).execute()
        service.auth.admin.delete_user(user_id)
        print("Cleanup done")


if __name__ == "__main__":
    asyncio.run(main())
