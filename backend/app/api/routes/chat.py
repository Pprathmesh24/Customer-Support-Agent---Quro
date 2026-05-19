import re

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import AIMessage, HumanMessage
from openai import AsyncOpenAI
from pydantic import BaseModel
from supabase import Client

from app.agent.cache import SemanticCache
from app.api.deps import get_current_user_id, get_graph, get_openai_client, get_service_client
from app.api.schemas import SourceRef
from app.db.messages import save_messages

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    conversation_id: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceRef]
    cached: bool = False


def _load_history(
    supabase: Client,
    conversation_id: str,
) -> list[HumanMessage | AIMessage]:
    """Loads prior turns from the messages table as LangChain message objects."""
    rows = (
        supabase.table("messages")
        .select("role, content")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
    )
    msgs: list[HumanMessage | AIMessage] = []
    for row in rows.data:
        if row["role"] == "user":
            msgs.append(HumanMessage(content=row["content"]))
        elif row["role"] == "assistant":
            msgs.append(AIMessage(content=row["content"]))
    return msgs


def _extract_sources(messages: list) -> list[SourceRef]:
    """
    Parses source citations from retriever ToolMessages.
    Expects lines in the format: '[N] Source: doc_name.pdf (page 5)'
    """
    sources: list[SourceRef] = []
    seen: set[tuple] = set()
    pattern = re.compile(r"^\[\d+\] Source: (.+?)(?:\s+\(page (\d+)\))?$")

    for msg in messages:
        if getattr(msg, "type", None) != "tool":
            continue
        if getattr(msg, "name", None) != "retriever":
            continue
        for line in msg.content.split("\n"):
            m = pattern.match(line.strip())
            if m:
                doc_name = m.group(1)
                page = int(m.group(2)) if m.group(2) else None
                key = (doc_name, page)
                if key not in seen:
                    seen.add(key)
                    sources.append(SourceRef(doc_name=doc_name, page_number=page))

    return sources


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_service_client),
    openai_client: AsyncOpenAI = Depends(get_openai_client),
    graph=Depends(get_graph),
) -> ChatResponse:
    # ── 1. Verify the conversation belongs to this user ───────────────────────
    conv = (
        supabase.table("conversations")
        .select("id")
        .eq("id", request.conversation_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not conv.data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # ── 2. Semantic cache check ───────────────────────────────────────────────
    cache = SemanticCache(supabase=supabase, openai_client=openai_client)
    cached_answer = await cache.check(request.message, user_id)
    if cached_answer:
        # Save cache hits to the messages table so history is complete.
        save_messages(
            supabase=supabase,
            conversation_id=request.conversation_id,
            user_content=request.message,
            assistant_content=cached_answer,
            sources=[],
        )
        return ChatResponse(answer=cached_answer, sources=[], cached=True)

    # ── 3. Load conversation history from DB ──────────────────────────────────
    history = _load_history(supabase, request.conversation_id)
    history.append(HumanMessage(content=request.message))

    # ── 4. Run the ReAct agent ────────────────────────────────────────────────
    result = await graph.ainvoke(
        {
            "messages": history,
            "conversation_id": request.conversation_id,
            "user_id": user_id,
        }
    )

    # ── 5. Extract answer and source citations ────────────────────────────────
    final_msg = result["messages"][-1]
    answer: str = (
        final_msg.content
        if isinstance(final_msg.content, str)
        else str(final_msg.content)
    )
    sources = _extract_sources(result["messages"])

    # ── 6. Persist both turns to the messages table ───────────────────────────
    save_messages(
        supabase=supabase,
        conversation_id=request.conversation_id,
        user_content=request.message,
        assistant_content=answer,
        sources=sources,
    )

    # ── 7. Store answer in semantic cache for future identical queries ─────────
    await cache.store(request.message, answer, user_id)

    return ChatResponse(answer=answer, sources=sources)
