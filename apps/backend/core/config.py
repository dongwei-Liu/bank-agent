from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator

# apps/backend/core/config.py -> project root is three levels up
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings.

    Values are read from the project root .env and can always be overridden
    by real environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Service
    service_name: str = "bank-agent-backend"
    host: str = "127.0.0.1"
    port: int = 8080

    # Apache Fineract
    fineract_base_url: str = "https://localhost:8443/fineract-provider"
    fineract_user: str = "mifos"
    fineract_password: str = "password"
    fineract_tenant: str = "default"
    fineract_verify_ssl: bool = False
    fineract_timeout_seconds: float = 10.0

    # Self-owned database (Agent state, actions, audit)
    database_url: str = "postgresql+psycopg://bank_agent@127.0.0.1:5432/bank_agent"
    environment: str = "development"
    otp_secret: str = ""
    dev_otp_inbox: bool = False
    demo_password: str = ""
    admin_password: str = ""
    card_encryption_key: str = ""
    max_report_transactions: int = 100000
    analysis_retention_hours: int = Field(default=24, gt=0, le=168)
    analysis_min_samples: int = Field(default=5, ge=5)
    analysis_daily_scope_limit: int = Field(default=10, gt=0, le=100)
    anomaly_model_directory: str = ".runtime/anomaly-models"
    anomaly_model_max_age_days: int = Field(default=90, gt=0, le=90)

    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    siliconflow_model: str = ""

    # Durable Agent conversations and the separate Agent worker.
    agent_conversation_retention_days: int = Field(default=30, ge=1, le=90)
    agent_run_lease_seconds: int = Field(default=300, ge=60, le=1800)
    agent_run_max_attempts: int = Field(default=3, ge=1, le=5)
    agent_sse_poll_seconds: float = Field(default=0.5, ge=0.1, le=5.0)
    agent_sse_max_seconds: int = Field(default=25, ge=5, le=60)

    @model_validator(mode="after")
    def validate_isolation(self):
        from sqlalchemy.engine import make_url

        if make_url(self.database_url).database in {
            "fineract_default",
            "fineract_tenants",
        }:
            raise ValueError("业务数据库必须独立于 Fineract 数据库")
        if self.dev_otp_inbox and self.environment != "development":
            raise ValueError("验证码收件箱仅限 development 环境")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
