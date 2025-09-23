from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Map the env var named DATABASE_URL to this field
    database_url: str = Field(alias="DATABASE_URL")

    # Pydantic v2-style config: read .env and ignore extra env vars
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # don't error on POSTGRES_USER/PASSWORD/DB
    )

settings = Settings()
