from functools import lru_cache

from pydantic import AliasChoices, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="Adwize")
    app_version: str = Field(default="0.1.0")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    api_prefix: str = Field(default="/api/v1")

    database_host: str = Field(
        default="localhost",
        validation_alias=AliasChoices("database_host", "db_host"),
    )
    database_port: int = Field(
        default=5432,
        validation_alias=AliasChoices("database_port", "db_port"),
    )
    database_name: str = Field(
        default="adwize",
        validation_alias=AliasChoices("database_name", "db_name"),
    )
    database_user: str = Field(
        default="postgres",
        validation_alias=AliasChoices("database_user", "db_user"),
    )
    database_password: str = Field(
        default="postgres",
        validation_alias=AliasChoices("database_password", "db_password"),
    )
    database_echo: bool = Field(default=False)

    api_key: str | None = Field(default=None)

    webhook_url: str | None = Field(default=None)

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
