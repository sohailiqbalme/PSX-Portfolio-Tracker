"""
run.py
─────────────────────────────────────────────────────────────────────────────
Development server entrypoint.

Usage:
    # Run with Flask CLI (recommended):
    flask --app run:app run --debug

    # Run directly:
    python run.py
─────────────────────────────────────────────────────────────────────────────
"""

from app import create_app

# The 'app' variable is required by `flask --app run:app`
app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=app.config.get("DEBUG", False),
    )
