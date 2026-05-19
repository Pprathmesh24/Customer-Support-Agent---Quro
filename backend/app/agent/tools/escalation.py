import asyncio
import base64
import logging
from typing import Any

import httpx
import resend
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from supabase import Client

logger = logging.getLogger(__name__)

_LINEAR_API_URL = "https://api.linear.app/graphql"

_CREATE_ISSUE_MUTATION = """
mutation CreateIssue($title: String!, $teamId: String!, $description: String) {
    issueCreate(input: {
        title: $title
        teamId: $teamId
        description: $description
    }) {
        success
        issue {
            id
            identifier
            url
        }
    }
}
"""


async def _create_linear_ticket(
    question: str,
    api_key: str,
    team_id: str,
) -> dict[str, str]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            _LINEAR_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "query": _CREATE_ISSUE_MUTATION,
                "variables": {
                    "title": f"[Unanswered] {question[:80]}",
                    "teamId": team_id,
                    "description": (
                        f"**Unanswered customer question:**\n\n{question}\n\n"
                        "_Automatically created by Quro escalation tool._"
                    ),
                },
            },
        )
        resp.raise_for_status()
        body: dict[str, Any] = resp.json()
        if errors := body.get("errors"):
            raise ValueError(f"Linear GraphQL error: {errors}")
        issue = body["data"]["issueCreate"]["issue"]
        return {"identifier": issue["identifier"], "url": issue["url"]}


async def _notify_slack(
    webhook_url: str,
    question: str,
    linear_url: str | None,
) -> None:
    text = f"*New escalation from Quro*\n*Question:* {question}"
    if linear_url:
        text += f"\n*Linear ticket:* {linear_url}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(webhook_url, json={"text": text})
        resp.raise_for_status()


_CRISP_API_URL = "https://api.crisp.chat/v1"


async def _handoff_to_crisp(
    website_id: str,
    identifier: str,
    key: str,
    question: str,
    linear_url: str | None,
) -> str:
    """Creates a Crisp conversation and posts an operator note, returning the inbox URL."""
    token = base64.b64encode(f"{identifier}:{key}".encode()).decode()
    headers = {
        "Authorization": f"Basic {token}",
        "X-Crisp-Tier": "plugin",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        conv_resp = await client.post(
            f"{_CRISP_API_URL}/website/{website_id}/conversation",
            headers=headers,
        )
        conv_resp.raise_for_status()
        session_id: str = conv_resp.json()["data"]["session_id"]

        body = f"Escalation from Quro\n\nUnanswered question:\n{question}"
        if linear_url:
            body += f"\n\nLinear ticket: {linear_url}"

        msg_resp = await client.post(
            f"{_CRISP_API_URL}/website/{website_id}/conversation/{session_id}/message",
            headers=headers,
            json={"type": "text", "from": "operator", "origin": "chat", "content": body},
        )
        msg_resp.raise_for_status()

    return f"https://app.crisp.chat/website/{website_id}/inbox/{session_id}"


async def _send_resend_email(
    api_key: str,
    from_email: str,
    to_email: str,
    question: str,
    linear_url: str | None,
) -> None:
    resend.api_key = api_key
    linear_section = (
        f'<p><a href="{linear_url}">View Linear ticket</a></p>' if linear_url else ""
    )
    params: resend.Emails.SendParams = {
        "from": from_email,
        "to": [to_email],
        "subject": f"[Quro] Unanswered question: {question[:60]}",
        "html": (
            "<p><strong>An unanswered customer question has been escalated:</strong></p>"
            f"<blockquote>{question}</blockquote>"
            f"{linear_section}"
            "<p><em>Sent by Quro escalation tool.</em></p>"
        ),
    }
    await resend.Emails.send_async(params)


class EscalationInput(BaseModel):
    question: str = Field(description="The unanswered question verbatim")
    conversation_id: str = Field(description="UUID of the current conversation")


class EscalationTool(BaseTool):
    """
    Escalates an unanswered question to the support team.

    Actions (each runs independently — one failure does not block the rest):
      1. Inserts a row into `knowledge_gaps` (always).
      2. Creates a Linear ticket (requires linear_api_key + linear_team_id).
      3. Inserts a row into `escalated_tickets` with the Linear ticket details.
      4. Sends a Slack notification (requires slack_webhook_url).
      5. Sends a Resend email (requires resend_api_key + support_team_email).
      6. Opens a Crisp live-chat conversation (requires crisp_website_id + crisp_identifier + crisp_key).
    """

    name: str = "escalation"
    description: str = (
        "Escalates an unanswered question to the support team. "
        "Logs the question to the knowledge gaps database and notifies the team via "
        "Linear, Slack, email, and Crisp live chat. "
        "Use this when the knowledge base does not contain an answer for the user's question."
    )
    args_schema: type[BaseModel] = EscalationInput
    supabase: Client = Field(exclude=True)
    linear_api_key: str = ""
    linear_team_id: str = ""
    slack_webhook_url: str = ""
    resend_api_key: str = ""
    resend_from_email: str = ""
    support_team_email: str = ""
    crisp_website_id: str = ""
    crisp_identifier: str = ""
    crisp_key: str = ""

    class Config:
        arbitrary_types_allowed = True

    def _run(self, question: str, conversation_id: str) -> str:
        return asyncio.run(self._arun(question, conversation_id))

    async def _arun(self, question: str, conversation_id: str) -> str:
        conv_resp = (
            self.supabase.table("conversations")
            .select("user_id")
            .eq("id", conversation_id)
            .single()
            .execute()
        )
        user_id: str = conv_resp.data["user_id"]

        # 1. Log knowledge gap.
        self.supabase.table("knowledge_gaps").insert(
            {"conversation_id": conversation_id, "question": question}
        ).execute()
        print(f"  [escalation] knowledge_gap logged")

        # 2. Create Linear ticket (optional).
        linear_id: str | None = None
        linear_url: str | None = None

        if self.linear_api_key and self.linear_team_id:
            try:
                ticket = await _create_linear_ticket(
                    question=question,
                    api_key=self.linear_api_key,
                    team_id=self.linear_team_id,
                )
                linear_id = ticket["identifier"]
                linear_url = ticket["url"]
                print(f"  [escalation] Linear ticket: {linear_id} ({linear_url})")
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                logger.warning("Linear ticket creation failed: %s", exc)
        else:
            logger.warning("LINEAR_API_KEY or LINEAR_TEAM_ID not set — skipping Linear")

        # 3. Record escalated ticket.
        self.supabase.table("escalated_tickets").insert(
            {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "title": question,
                "linear_ticket_id": linear_id,
                "linear_ticket_url": linear_url,
            }
        ).execute()
        print(f"  [escalation] escalated_tickets row created")

        # 4 + 5. Slack and Resend — fire concurrently, each failure is independent.
        notifications: list[Any] = []

        if self.slack_webhook_url:
            notifications.append(
                _notify_slack(
                    webhook_url=self.slack_webhook_url,
                    question=question,
                    linear_url=linear_url,
                )
            )
        else:
            logger.warning("SLACK_WEBHOOK_URL not set — skipping Slack notification")

        if self.resend_api_key and self.support_team_email:
            notifications.append(
                _send_resend_email(
                    api_key=self.resend_api_key,
                    from_email=self.resend_from_email,
                    to_email=self.support_team_email,
                    question=question,
                    linear_url=linear_url,
                )
            )
        else:
            logger.warning("RESEND_API_KEY or SUPPORT_TEAM_EMAIL not set — skipping email")

        crisp_url: str | None = None
        crisp_index: int | None = None
        if self.crisp_website_id and self.crisp_identifier and self.crisp_key:
            crisp_index = len(notifications)
            notifications.append(
                _handoff_to_crisp(
                    website_id=self.crisp_website_id,
                    identifier=self.crisp_identifier,
                    key=self.crisp_key,
                    question=question,
                    linear_url=linear_url,
                )
            )
        else:
            logger.warning(
                "CRISP_WEBSITE_ID / CRISP_IDENTIFIER / CRISP_KEY not set — skipping Crisp"
            )

        if notifications:
            results = await asyncio.gather(*notifications, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.warning("Notification %d failed: %s", i, result)
                else:
                    print(f"  [escalation] notification {i + 1}/{len(notifications)} sent")
                    if i == crisp_index and isinstance(result, str):
                        crisp_url = result

        parts: list[str] = ["I've escalated your question to the support team."]
        if linear_url:
            parts.append(f"Linear ticket: {linear_id} — {linear_url}")
        if crisp_url:
            parts.append(f"Live chat: {crisp_url}")
        parts.append("Someone will follow up with you shortly.")
        return "\n".join(parts)
