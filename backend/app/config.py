from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://tradeoff:tradeoff@localhost:55432/tradeoff"
    app_env: Literal["dev", "test", "prod"] = "prod"
    credential_key: str = ""
    migrations_dir: str = ""
    # None means "on everywhere except tests"; set explicitly to override.
    replay_runner_enabled: bool | None = None

    @property
    def runner_enabled(self) -> bool:
        if self.replay_runner_enabled is not None:
            return self.replay_runner_enabled
        return self.app_env != "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()
