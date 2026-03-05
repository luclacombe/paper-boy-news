"""Paper Boy API — FastAPI entry point."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.build import router as build_router
from api.routes.deliver import router as deliver_router
from api.routes.feeds import router as feeds_router
from api.routes.smtp_test import router as smtp_test_router

app = FastAPI(title="Paper Boy API")

# Build CORS origins: localhost for dev, plus any configured production origins.
# ALLOWED_ORIGINS supports comma-separated values (e.g. for Vercel production + preview URLs).
# Falls back to single ALLOWED_ORIGIN for backwards compatibility.
_allowed = os.getenv("ALLOWED_ORIGINS", os.getenv("ALLOWED_ORIGIN", ""))
_origins = ["http://localhost:3000"] + [
    o.strip() for o in _allowed.split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(build_router)
app.include_router(deliver_router)
app.include_router(smtp_test_router)
app.include_router(feeds_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
