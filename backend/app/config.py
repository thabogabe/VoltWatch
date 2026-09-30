from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://voltwatch:voltwatch@localhost:5432/voltwatch"
    # Optional Postgres schema to keep VoltWatch's tables (and PostGIS) separate when
    # sharing a database with another app. Empty = the default "public" schema.
    db_schema: str = ""
    # Shared code community patrol officers enter to update report status.
    # Empty = status updates are switched off.
    patrol_code: str = ""
    cors_origins: str = "http://localhost:5173"

    @field_validator("db_schema", "database_url", "patrol_code")
    @classmethod
    def strip_pasted_value(cls, value: str) -> str:
        # Values pasted into hosting dashboards often carry spaces, newlines or quotes.
        return value.strip().strip("\"'").strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
