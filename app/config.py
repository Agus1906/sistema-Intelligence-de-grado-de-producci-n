"""Configuración validada; nunca registrar secretos."""
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    storage_backend: Literal['redis', 'sqlite'] = 'sqlite'
    sqlite_path: str = 'data/tasks.sqlite'
    checkpoint_path: str = 'data/checkpoints.sqlite'
    redis_url: str = 'redis://localhost:6379/0'
    api_key: SecretStr
    approval_key: SecretStr
    agent_mode: Literal['offline', 'llm'] = 'offline'
    llm_provider: Literal['openai', 'anthropic'] = 'openai'
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = ''
    openai_api_key: SecretStr | None = None
    openai_model: str = ''
    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str = 'intelligence-final'
    worker_concurrency: int = 5
    job_timeout: int = 180


@lru_cache
def settings():
    return Settings()
