"""Application settings. Every value comes from an environment variable."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    environment: Literal["development", "production"] = "development"

    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "picnic_permit"
    postgres_user: str
    postgres_password: SecretStr
    db_connect_timeout_seconds: int = 3

    # Rules and displays use this zone. Timestamps are stored in UTC.
    app_timezone: str = "Asia/Kolkata"

    # Uploaded files live on a Docker volume mounted here.
    upload_dir: str = "/data/uploads"

    # Folder with the master CSV files read by `python -m app.seeds.load_masters`.
    masters_dir: str = "/masters"

    # Address of the site as the public reaches it. Used in links sent by SMS.
    public_base_url: str = "http://localhost:3000"

    # Send the login cookie only over HTTPS. Must be true once the site has HTTPS.
    session_cookie_secure: bool = False

    # The login captcha can be switched off for automated tests and load tests,
    # never in production.
    captcha_enabled: bool = True

    @model_validator(mode="after")
    def _captcha_is_mandatory_in_production(self) -> Settings:
        if self.environment == "production" and not self.captcha_enabled:
            raise ValueError("CAPTCHA_ENABLED cannot be false in production")
        return self

    @property
    def database_url(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
