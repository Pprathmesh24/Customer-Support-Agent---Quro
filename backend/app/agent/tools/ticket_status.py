import asyncio

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from supabase import Client


class TicketStatusInput(BaseModel):
    conversation_id: str = Field(description="UUID of the current conversation")


class TicketStatusTool(BaseTool):
    """Returns the current status of an escalated support ticket for this conversation."""

    name: str = "ticket_status"
    description: str = (
        "Returns the current status of a previously escalated support ticket for this "
        "conversation. Use when the customer asks about the status of their escalated issue."
    )
    args_schema: type[BaseModel] = TicketStatusInput
    supabase: Client = Field(exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def _run(self, conversation_id: str) -> str:
        return asyncio.run(self._arun(conversation_id))

    async def _arun(self, conversation_id: str) -> str:
        result = (
            self.supabase.table("escalated_tickets")
            .select("status, created_at, resolved_at")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not result.data:
            return "No escalated ticket found for this conversation."
        status: str = result.data[0]["status"]
        if status == "open":
            return "Status: open. Your ticket has been received and is queued for review."
        if status == "in_progress":
            return "Status: in progress. The support team is actively working on your ticket."
        if status == "resolved":
            return "Status: resolved. The support team has resolved your ticket."
        return f"Status: {status}."
