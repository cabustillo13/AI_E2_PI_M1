from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    llm_provider: str = "openai"
    llm_model: str = "gpt-5-mini"

    prompt_version: str = "v3"

    max_retries: int = 2
    max_input_chars: int = 4000

    metrics_path: str = "data/metrics.jsonl"
    prompts_path: str = "prompts"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()