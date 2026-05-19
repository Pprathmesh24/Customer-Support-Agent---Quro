from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import Client

from app.api.deps import get_current_user_id, get_service_client
from app.api.schemas import SourceRef
from app.db.messages import get_messages

router = APIRouter()


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    sources: list[SourceRef]
    created_at: str


class ConversationHistoryResponse(BaseModel):
    conversation_id: str
    messages: list[MessageOut]


@router.get("/conversations/{conversation_id}", response_model=ConversationHistoryResponse)
async def get_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_service_client),
) -> ConversationHistoryResponse:
    # Verify the conversation belongs to this user.
    conv = (
        supabase.table("conversations")
        .select("id")
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not conv.data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    rows = get_messages(supabase, conversation_id)

    messages = [
        MessageOut(
            id=row["id"],
            role=row["role"],
            content=row["content"],
            sources=[
                SourceRef(**s) for s in (row["sources"] or [])
            ],
            created_at=row["created_at"],
        )
        for row in rows
    ]

    return ConversationHistoryResponse(
        conversation_id=conversation_id,
        messages=messages,
    )
