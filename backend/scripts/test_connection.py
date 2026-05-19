"""
Verifies the Supabase connection end-to-end:
  1. Connects with the service role key
  2. Creates a temporary auth user
  3. Inserts a conversation row, reads it back, deletes it
  4. Deletes the temporary user
  5. Confirms all 6 tables are reachable

Usage:
    uv run scripts/test_connection.py
"""
from pathlib import Path

from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parents[2] / ".env")

from supabase import create_client, Client  # noqa: E402


TEST_EMAIL = "test-connection-script@example.com"
TEST_PASSWORD = "test-connection-script-pw-1234"


def check_tables(client: Client) -> None:
    tables = [
        "documents",
        "document_chunks",
        "conversations",
        "messages",
        "escalated_tickets",
        "knowledge_gaps",
    ]
    for table in tables:
        result = client.table(table).select("*", count="exact").limit(0).execute()
        print(f"  {table}: reachable (rows={result.count})")


def test_insert_read_delete(client: Client) -> None:
    # Create a temporary auth user so FK on conversations.user_id is satisfied.
    user_resp = client.auth.admin.create_user(
        {"email": TEST_EMAIL, "password": TEST_PASSWORD, "email_confirm": True}
    )
    user_id: str = user_resp.user.id
    print(f"  temp user created: {user_id}")

    try:
        # Insert
        insert_result = (
            client.table("conversations")
            .insert({"user_id": user_id, "title": "connection-test"})
            .execute()
        )
        conv_id: str = insert_result.data[0]["id"]
        print(f"  inserted conversation: {conv_id}")

        # Read back
        read_result = (
            client.table("conversations").select("id, title").eq("id", conv_id).execute()
        )
        assert read_result.data[0]["title"] == "connection-test", "Read-back mismatch"
        print("  read-back: OK")

        # Delete row
        client.table("conversations").delete().eq("id", conv_id).execute()
        print("  deleted conversation: OK")

    finally:
        client.auth.admin.delete_user(user_id)
        print(f"  temp user deleted: {user_id}")


def main() -> None:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    client: Client = create_client(url, key)

    print("Checking table reachability...")
    check_tables(client)

    print("\nRunning insert → read → delete cycle...")
    test_insert_read_delete(client)

    print("\nConnection OK")


if __name__ == "__main__":
    main()
