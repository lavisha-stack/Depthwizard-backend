"""FastAPI application entry point."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from config import CORS_ORIGINS, MAX_UPLOAD_SIZE_MB, RUNTIME_DIR

logging.basicConfig(level=logging.INFO, format="%(message)s")
RUNTIME_DIR.joinpath("jobs").mkdir(parents=True, exist_ok=True)
logging.getLogger("depthwizard").info("[DepthWizard] Maximum image upload: %s MB", MAX_UPLOAD_SIZE_MB)

app = FastAPI(title="DepthWizard Backend", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "DepthWizard Backend"}
