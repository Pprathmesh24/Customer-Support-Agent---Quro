from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from supabase import Client

from app.api.deps import get_current_user_id, get_service_client
from app.api.schemas import SourceRef
from app.db.messages import get_messages

router = APIRouter(prefix="/admin", tags=["admin"])


class EscalationOut(BaseModel):
    id: str
    conversation_id: str
    user_id: str
    title: str
    linear_ticket_id: str | None
    linear_ticket_url: str | None
    status: str
    created_at: str
    resolved_at: str | None


class KnowledgeGapOut(BaseModel):
    question: str
    count: int
    last_seen: str


class EscalationsResponse(BaseModel):
    items: list[EscalationOut]
    total: int


class KnowledgeGapsResponse(BaseModel):
    items: list[KnowledgeGapOut]
    total: int


class UpdateEscalationRequest(BaseModel):
    status: Literal["open", "in_progress", "resolved"]


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    sources: list[SourceRef]


class EscalationConversationResponse(BaseModel):
    conversation_id: str
    messages: list[MessageOut]


@router.get("/escalations", response_model=EscalationsResponse)
async def list_escalations(
    status: str | None = Query(None, description="open | in_progress | resolved"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_service_client),
) -> EscalationsResponse:
    query = supabase.table("escalated_tickets").select("*", count="exact")
    if status:
        query = query.eq("status", status)
    result = (
        query.order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return EscalationsResponse(items=result.data, total=result.count or 0)


@router.get("/escalations/{escalation_id}", response_model=EscalationOut)
async def get_escalation(
    escalation_id: str,
    _user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_service_client),
) -> EscalationOut:
    result = (
        supabase.table("escalated_tickets")
        .select("*")
        .eq("id", escalation_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Escalation not found")
    return EscalationOut(**result.data)


@router.patch("/escalations/{escalation_id}", response_model=EscalationOut)
async def update_escalation_status(
    escalation_id: str,
    body: UpdateEscalationRequest,
    _user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_service_client),
) -> EscalationOut:
    updates: dict[str, str | None] = {"status": body.status}
    if body.status == "resolved":
        updates["resolved_at"] = datetime.now(timezone.utc).isoformat()
    elif body.status in ("open", "in_progress"):
        updates["resolved_at"] = None
    result = (
        supabase.table("escalated_tickets")
        .update(updates)
        .eq("id", escalation_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Escalation not found")
    return EscalationOut(**result.data[0])


@router.get("/escalations/{escalation_id}/conversation", response_model=EscalationConversationResponse)
async def get_escalation_conversation(
    escalation_id: str,
    _user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_service_client),
) -> EscalationConversationResponse:
    esc = (
        supabase.table("escalated_tickets")
        .select("conversation_id")
        .eq("id", escalation_id)
        .single()
        .execute()
    )
    if not esc.data:
        raise HTTPException(status_code=404, detail="Escalation not found")
    conversation_id: str = esc.data["conversation_id"]
    rows = get_messages(supabase, conversation_id)
    messages = [
        MessageOut(
            id=r["id"],
            role=r["role"],
            content=r["content"],
            sources=[SourceRef(**s) for s in (r["sources"] or [])],
        )
        for r in rows
    ]
    return EscalationConversationResponse(conversation_id=conversation_id, messages=messages)


@router.get("/knowledge-gaps", response_model=KnowledgeGapsResponse)
async def list_knowledge_gaps(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_service_client),
) -> KnowledgeGapsResponse:
    items_result = supabase.rpc(
        "get_knowledge_gap_summary",
        {"p_limit": limit, "p_offset": offset},
    ).execute()
    count_result = supabase.rpc("get_knowledge_gap_count", {}).execute()
    total: int = count_result.data if isinstance(count_result.data, int) else 0
    return KnowledgeGapsResponse(items=items_result.data, total=total)
