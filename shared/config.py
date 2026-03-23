from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "mcp_soc"

    # AWS
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET: str = "mcp-soc-raw-logs"

    # Firebase
    FIREBASE_SERVICE_ACCOUNT_PATH: str = "config/firebase-service-account.json"

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # SendGrid
    SENDGRID_API_KEY: str = ""
    ALERT_FROM_EMAIL: str = "alerts@mcp-soc.io"

    # App
    FRONTEND_URL: str = "http://localhost:3000"
    API_BASE_URL: str = "http://localhost:8000"

    # Correlation
    CORRELATION_WINDOW_MINUTES: int = 60

    # Risk score multipliers
    RISK_PRIVILEGE_HIGH: float = 2.0
    RISK_PRIVILEGE_LOW: float = 1.0
    RISK_ASSET_CRITICAL: float = 2.0
    RISK_ASSET_LOW: float = 1.0

    # GeoIP
    GEOIP_DB_PATH: str = "data/GeoLite2-City.mmdb"

    # IOC Enrichment
    ABUSEIPDB_API_KEY: str = ""
    VIRUSTOTAL_API_KEY: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
