from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPENSE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AI_PROVIDER", "fallback")
    from app.database import init_db, reset_engine
    from app.seed import seed_defaults
    from app.database import get_session_factory

    reset_engine()
    init_db()
    db = get_session_factory()()
    try:
        seed_defaults(db)
    finally:
        db.close()

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
    reset_engine()
