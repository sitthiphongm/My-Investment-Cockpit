"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "My Investment Cockpit API"
    debug: bool = False
    secret_key: str = "change-me-in-production"

    # Database (PostgreSQL)
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/investment_history"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000", "http://localhost"]

    # OAuth - Google
    google_client_id: str = ""
    google_client_secret: str = ""

    # OAuth - Facebook
    facebook_client_id: str = ""
    facebook_client_secret: str = ""

    # OAuth redirect base URL
    oauth_redirect_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost"

    # ─── Market Data Providers ───────────────────────────────────────────
    market_data_provider: str = "fmp"  # fmp, alpha_vantage, twelve_data, eodhd, yfinance
    market_data_fallback: str = "yfinance"
    fmp_api_key: str = ""
    alpha_vantage_api_key: str = ""
    twelve_data_api_key: str = ""
    eodhd_api_key: str = ""

    # ─── FX Rates ────────────────────────────────────────────────────────
    fx_provider: str = "manual"  # unirate, alpha_vantage, manual
    fx_api_key: str = ""
    fx_cache_ttl_hours: int = 24

    # ─── Cache TTL (seconds) ─────────────────────────────────────────────
    market_data_cache_ttl: int = 3600  # 1 hour
    trending_cache_ttl: int = 900  # 15 minutes

    # ─── Provider Resilience ─────────────────────────────────────────────
    provider_circuit_breaker_threshold: int = 5
    provider_circuit_breaker_timeout: int = 300  # seconds
    provider_rate_limit_per_minute: int = 30

    # ─── Email Notifications ─────────────────────────────────────────────
    email_provider: str = "smtp"  # smtp, sendgrid, mailgun, ses
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True
    sendgrid_api_key: str = ""
    alert_email_enabled: bool = False
    email_dev_mode: bool = True  # Write to logs instead of sending

    # ─── AI Insights ─────────────────────────────────────────────────────
    ai_provider: str = "disabled"  # disabled, rule_based, local_llm, hosted_llm
    ai_local_model_path: str = ""
    ai_hosted_api_key: str = ""
    ai_hosted_endpoint: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
