from functools import lru_cache

from fastapi import Header, HTTPException
from openai import AsyncOpenAI
from supabase import Client, create_client

from app.core.settings import settings


async def get_current_user_id(authorization: str = Header(...)) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.removeprefix("Bearer ")
    supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
    try:
        resp = supabase.auth.get_user(token)
        if resp.user is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return resp.user.id
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_service_client() -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def get_openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.openai_api_key)


@lru_cache(maxsize=1)
def get_graph():
    """
    Builds and caches the LangGraph agent for the lifetime of the process.
    The cross-encoder model (~85 MB) and all tool instances are created once.
    """
    from app.agent.graph import build_graph

    service = create_client(settings.supabase_url, settings.supabase_service_role_key)
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return build_graph(
        supabase=service,
        openai_client=openai_client,
        anthropic_api_key=settings.anthropic_api_key,
        llm_model=settings.llm_model,
        linear_api_key=settings.linear_api_key,
        linear_team_id=settings.linear_team_id,
        slack_webhook_url=settings.slack_webhook_url,
        resend_api_key=settings.resend_api_key,
        resend_from_email=settings.resend_from_email,
        support_team_email=settings.support_team_email,
        crisp_website_id=settings.crisp_website_id,
        crisp_identifier=settings.crisp_identifier,
        crisp_key=settings.crisp_key,
    )
