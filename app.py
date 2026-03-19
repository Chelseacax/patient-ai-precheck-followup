"""
MedBridge — Multilingual Healthcare Communication Platform
==========================================================
Singapore / Southeast Asian Context

This file is the orchestration layer only:
  - Creates the Flask app
  - Initialises extensions (DB)
  - Registers all route blueprints
  - Runs DB migrations on first start

All business logic lives in the dedicated modules:
  llm/        — LLM provider resolution and API calls
  agent/      — Agentic loop, tool definitions, HealthHub bridge
  language/   — Language detection and configuration
  data/       — Mock data (doctors, slots)
  routes/     — Flask blueprints (one file per feature area)
  models.py   — SQLAlchemy models
  extensions.py — Shared db singleton
"""

import os
import logging

from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

from extensions import db
from routes import register_routes

load_dotenv()

# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> Flask:
    app = Flask(__name__, static_folder="static")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///medbridge.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.json.sort_keys = False  # preserve insertion order for language dropdown

    CORS(app)
    db.init_app(app)

    register_routes(app)

    with app.app_context():
        _migrate_db()

    return app


# ── DB migrations (idempotent) ────────────────────────────────────────────────

def _migrate_db():
    """Apply schema migrations needed for existing databases."""
    # Rename old appointment table if it has the wrong schema
    try:
        cols = [row[1] for row in db.session.execute(
            db.text("PRAGMA table_info(appointment)")).fetchall()]
        if cols and "patient_id" not in cols:
            db.session.execute(db.text("ALTER TABLE appointment RENAME TO old_booking_appointment"))
            db.session.commit()
    except Exception:
        db.session.rollback()

    db.create_all()

    # Add columns that may not exist in older databases
    _add_column_if_missing("session", "is_urgent", "BOOLEAN DEFAULT 0")
    _add_column_if_missing("appointment", "symptom_summary", "TEXT")


def _add_column_if_missing(table: str, column: str, definition: str):
    try:
        db.session.execute(db.text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
        db.session.commit()
    except Exception:
        db.session.rollback()


# ── Entry point ───────────────────────────────────────────────────────────────

app = create_app()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    port = int(os.getenv("PORT", 5001))
    app.run(debug=True, port=port)
