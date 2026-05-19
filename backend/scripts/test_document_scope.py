"""
Tests DocumentScopeTool against real Supabase data.
Inserts two sample document rows, calls the tool, verifies output, then cleans up.
Usage: uv run scripts/test_document_scope.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from supabase import create_client

from app.agent.tools.document_scope import DocumentScopeTool
from app.core.settings import settings

TEST_EMAIL = "test-scope@example.com"
TEST_PASSWORD = "test-scope-pw-1111"


async def main() -> None:
    service = create_client(settings.supabase_url, settings.supabase_service_role_key)

    user_resp = service.auth.admin.create_user(
        {"email": TEST_EMAIL, "password": TEST_PASSWORD, "email_confirm": True}
    )
    user_id: str = user_resp.user.id
    print(f"Temp user: {user_id}")

    doc_ids: list[str] = []
    try:
        docs = (
            service.table("documents")
            .insert([
                {
                    "user_id": user_id,
                    "name": "product-manual.pdf",
                    "file_path": "test/product-manual.pdf",
                    "file_type": "pdf",
                    "category": "Product",
                    "chunk_count": 42,
                },
                {
                    "user_id": user_id,
                    "name": "billing-faq.txt",
                    "file_path": "test/billing-faq.txt",
                    "file_type": "txt",
                    "category": "Billing",
                    "chunk_count": 8,
                },
            ])
            .execute()
        )
        doc_ids = [d["id"] for d in docs.data]

        tool = DocumentScopeTool(supabase=service)
        result = tool._run()

        print("\nTool output:")
        print(result)

        assert "product-manual.pdf" in result
        assert "billing-faq.txt" in result
        assert "Product" in result
        assert "Billing" in result

        print("\nDocumentScopeTool OK")

    finally:
        for doc_id in doc_ids:
            service.table("documents").delete().eq("id", doc_id).execute()
        service.auth.admin.delete_user(user_id)
        print("Cleanup done")


if __name__ == "__main__":
    asyncio.run(main())
