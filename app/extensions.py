"""
app/extensions.py
─────────────────────────────────────────────────────────────────────────────
Shared Flask extension instances.

These are created here (without an app) and initialised later inside the
application factory (app/__init__.py) using the init_app() pattern.
This prevents circular imports between models, services, and the factory.
─────────────────────────────────────────────────────────────────────────────
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# ── SQLAlchemy ────────────────────────────────────────────────────────────────
# Single shared db instance used by all models.
db = SQLAlchemy()

# ── Flask-Migrate ─────────────────────────────────────────────────────────────
# Handles Alembic migration generation and application.
migrate = Migrate()
