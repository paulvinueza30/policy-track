"""Environment settings. Read secrets only from here (AGENTS.md §11)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    congress_api_key: str = ""
    news_api_key: str = ""

    deepseek_base_url: str = ""
    deepseek_api_key: str = ""
    deepseek_model: str = ""
    deepseek_timeout_seconds: float = 60.0  # keep below the 65 s AI timeout in frontend/lib/api.js
    deepseek_max_concurrent: int = 1  # one at a time on a single small GPU

    firebase_project_id: str = ""
    firebase_client_email: str = ""
    firebase_private_key: str = ""

    frontend_origin: str = "http://localhost:3000"


settings = Settings()
