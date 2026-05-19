from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parents[3] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    supabase_url: str
    supabase_service_role_key: str
    supabase_anon_key: str
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    llm_model: str = "claude-haiku-4-5-20251001"
    linear_api_key: str = ""
    linear_team_id: str = ""
    slack_webhook_url: str = ""
    resend_api_key: str = ""
    resend_from_email: str = "support@yourdomain.com"
    support_team_email: str = ""
    crisp_website_id: str = ""
    crisp_identifier: str = ""
    crisp_key: str = ""
    allowed_origins: list[str] = ["http://localhost:3000"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
