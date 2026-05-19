from supabase import Client

from app.api.schemas import SourceRef


def save_messages(
    supabase: Client,
    conversation_id: str,
    user_content: str,
    assistant_content: str,
    sources: list[SourceRef] | None = None,
) -> None:
    """Inserts the user turn and the assistant response in a single batch."""
    rows = [
        {
            "conversation_id": conversation_id,
            "role": "user",
            "content": user_content,
        },
        {
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": assistant_content,
            "sources": (
                [s.model_dump() for s in sources] if sources else []
            ),
        },
    ]
    supabase.table("messages").insert(rows).execute()

    # Keep conversations.updated_at current so the sidebar can sort by recency.
    supabase.table("conversations").update({"updated_at": "now()"}).eq(
        "id", conversation_id
    ).execute()


def get_messages(supabase: Client, conversation_id: str) -> list[dict]:
    """Returns all messages for a conversation ordered oldest-first."""
    result = (
        supabase.table("messages")
        .select("id, role, content, sources, created_at")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
    )
    return result.data or []
