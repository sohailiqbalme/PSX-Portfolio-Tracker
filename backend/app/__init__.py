"""
app/__init__.py
─────────────────────────────────────────────────────────────────────────────
Flask Application Factory

Pattern: create_app()
    - Reads config from app/config.py based on FLASK_ENV env var
    - Initialises SQLAlchemy, Flask-Migrate
    - Registers all Blueprints
    - Sets up structured logging

Usage:
    # Dev server
    flask --app run:app run

    # Unit tests
    from app import create_app
    app = create_app("testing")
─────────────────────────────────────────────────────────────────────────────
"""

import logging
import sys

import colorlog

from flask import Flask

from app.config import config_map, DevelopmentConfig
from app.extensions import db, migrate


def _configure_logging(log_level: str) -> None:
    """
    Set up coloured, structured logging for the application.

    Uses colorlog for console output so log levels are visually distinct
    during development. In production, replace with a JSON formatter and
    ship logs to your observability stack.
    """
    handler = colorlog.StreamHandler(sys.stdout)
    handler.setFormatter(
        colorlog.ColoredFormatter(
            fmt=(
                "%(log_color)s%(asctime)s [%(levelname)-8s] "
                "%(name)s - %(message)s%(reset)s"
            ),
            datefmt="%Y-%m-%dT%H:%M:%S",
            log_colors={
                "DEBUG":    "cyan",
                "INFO":     "green",
                "WARNING":  "yellow",
                "ERROR":    "red",
                "CRITICAL": "bold_red",
            },
        )
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root_logger.handlers.clear()
    root_logger.addHandler(handler)


def create_app(config_name: str | None = None) -> Flask:
    """
    Flask application factory.

    Args:
        config_name: One of 'development', 'testing', 'production'.
                     Defaults to the value of the FLASK_ENV env variable,
                     falling back to 'development'.

    Returns:
        A fully configured Flask application instance.
    """
    app = Flask(__name__, instance_relative_config=False)

    # ── Load config ───────────────────────────────────────────────────────────
    import os
    env = config_name or os.environ.get("FLASK_ENV", "development")
    config_class = config_map.get(env, DevelopmentConfig)
    config_obj = config_class()
    app.config.from_object(config_obj)

    # ── Configure logging ─────────────────────────────────────────────────────
    _configure_logging(app.config.get("LOG_LEVEL", "INFO"))
    logger = logging.getLogger(__name__)
    logger.info("Starting PSX Portfolio Tracker [env=%s]", env)

    # ── Initialise extensions ─────────────────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)

    # ── Import models so Flask-Migrate can detect them ────────────────────────
    # These imports must happen after db.init_app() to avoid circular imports.
    with app.app_context():
        from app.models import Portfolio, Transaction, DailyPrice, CompanyMetadata  # noqa: F401

    # ── Register Blueprints ───────────────────────────────────────────────────
    from app.api.routes import api_bp
    app.register_blueprint(api_bp)

    logger.info(
        "Registered blueprint: %s (prefix=%s)",
        api_bp.name,
        api_bp.url_prefix,
    )

    # ── Shell context ─────────────────────────────────────────────────────────
    # Makes db and models available in `flask shell` automatically.
    @app.shell_context_processor
    def make_shell_context():
        from app.models import Portfolio, Transaction, DailyPrice, CompanyMetadata
        return {
            "db": db,
            "Portfolio": Portfolio,
            "Transaction": Transaction,
            "DailyPrice": DailyPrice,
            "CompanyMetadata": CompanyMetadata,
        }

    return app
