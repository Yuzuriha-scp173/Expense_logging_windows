from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.expenses import router as expenses_router
from app.api.routes import assistant_router, categories_router, misc_router, settings_router, summary_router
from app.database import get_session_factory, init_db
from app.seed import seed_defaults

app = FastAPI(title="Daybook", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8765",
        "http://127.0.0.1:8765",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(expenses_router)
app.include_router(summary_router)
app.include_router(settings_router)
app.include_router(categories_router)
app.include_router(assistant_router)
app.include_router(misc_router)


@app.on_event("startup")
def startup() -> None:
    init_db()
    db = get_session_factory()()
    try:
        seed_defaults(db)
    finally:
        db.close()


def _frontend_dir() -> Path | None:
    candidates = []
    env = os.environ.get("DAYBOOK_UI")
    if env:
        candidates.append(Path(env))
    candidates.append(Path(__file__).resolve().parents[2] / "frontend" / "dist")
    for path in candidates:
        if path.exists():
            return path
    return None


frontend_dist = _frontend_dir()
if frontend_dist is not None:
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="ui")
