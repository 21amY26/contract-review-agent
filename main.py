"""
main.py

FastAPI entrypoint. Run with:
    uvicorn main:app --reload --port 8000
"""
from __future__ import annotations

import logging

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env BEFORE importing anything that reads os.getenv() at import time
# (agents/llm_router.py reads GROQ_API_KEY etc. at module load).
load_dotenv()

from api import analyze, database, models, auth  # noqa: E402  (import after load_dotenv on purpose)

# Create tables
models.Base.metadata.create_all(bind=database.engine)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("contract_review.api")

app = FastAPI(
    title="Contract Review API",
    version="0.1.0",
    description="API layer over the multi-agent contract review pipeline.",
)

# Vite dev server default port. Add your deployed frontend origin later.
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(analyze.router)


@app.get("/health")
async def health() -> dict:
    """Simple liveness check — useful once this is behind Docker/a host."""
    return {"status": "ok"}
