"""
app/config.py
─────────────────────────────────────────────────────────────────────────────
Environment-based configuration classes for the PSX Portfolio Tracker.

Usage:
    Instantiated automatically by the application factory in app/__init__.py
    based on the FLASK_ENV environment variable.

Config hierarchy:
    BaseConfig → DevelopmentConfig / TestingConfig / ProductionConfig
─────────────────────────────────────────────────────────────────────────────
"""

import os
from dotenv import load_dotenv

# Load .env file from the project root (one level above /app)
load_dotenv(override=True)


class BaseConfig:
    """Shared configuration for all environments."""

    # ── Flask Core ────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")

    # ── Database ──────────────────────────────────────────────────────────────
    # Supabase provides a standard PostgreSQL connection string.
    # SQLAlchemy requires the scheme to be 'postgresql+psycopg2' (not 'postgres').
    _raw_db_url: str = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:password@localhost:5432/psx_tracker",
    )
    # Supabase (and Heroku) export 'postgres://' which must be rewritten for SQLAlchemy 2.x
    SQLALCHEMY_DATABASE_URI: str = _raw_db_url.replace(
        "postgres://", "postgresql+psycopg2://", 1
    ).replace("postgresql://", "postgresql+psycopg2://", 1)

    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # Connection pool settings — tuned for Supabase's connection limits
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "pool_size": 5,
        "max_overflow": 10,
        "pool_pre_ping": True,   # Validates connections before use
        "pool_recycle": 300,     # Recycle connections every 5 minutes
    }

    # ── Price Ingestion ───────────────────────────────────────────────────────
    INGESTION_LOOKBACK_DAYS: int = int(os.environ.get("INGESTION_LOOKBACK_DAYS", 30))
    DEFAULT_TICKERS: list[str] = [
        t.strip()
        for t in os.environ.get(
            "DEFAULT_TICKERS", "ENGRO,HUBC,LUCK,MCB,OGDC"
        ).split(",")
    ]

    # ── Supabase Auth ─────────────────────────────────────────────────────────
    # JWT Secret: Supabase Dashboard > Settings > API > JWT Secret (HS256 key)
    # This is NOT the service_role or anon key — it is the raw signing secret.
    SUPABASE_JWT_SECRET: str = os.environ.get("SUPABASE_JWT_SECRET", "")
    # Public project URL (used for reference / future RLS integrations)
    SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")


class DevelopmentConfig(BaseConfig):
    """Development environment — verbose logging, debug mode."""

    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"


class TestingConfig(BaseConfig):
    """Testing environment — uses an in-memory SQLite DB so no Supabase needed."""

    TESTING: bool = True
    # SQLite for fast, isolated unit tests (no network dependency)
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS: dict = {}  # Override pool options for SQLite
    LOG_LEVEL: str = "WARNING"
    WTF_CSRF_ENABLED: bool = False


class ProductionConfig(BaseConfig):
    """Production environment — strict, minimal logging."""

    DEBUG: bool = False
    LOG_LEVEL: str = "WARNING"


# ── Config selector ───────────────────────────────────────────────────────────
config_map: dict[str, type] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config() -> BaseConfig:
    """
    Return the appropriate config class instance based on FLASK_ENV.

    Defaults to DevelopmentConfig if FLASK_ENV is not set.
    """
    env = os.environ.get("FLASK_ENV", "development").lower()
    config_class = config_map.get(env, DevelopmentConfig)
    return config_class()
