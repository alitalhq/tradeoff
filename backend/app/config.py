from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://tradeoff:tradeoff@localhost:55432/tradeoff"
    app_env: Literal["dev", "test", "prod"] = "prod"
    credential_key: str = ""
    migrations_dir: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
