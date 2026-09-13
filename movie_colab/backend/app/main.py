"""
app/main.py
FastAPI application factory with CORS middleware and lifespan.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    # Startup: nothing to initialise — telemetry registry is module-level.
    yield
    # Shutdown: in-flight asyncio tasks are cancelled by the event loop.


def create_app() -> FastAPI:
    app = FastAPI(
        title="Direct-to-Drive Cloud Ingestion Engine",
        version="1.0.0",
        description=(
            "Streams any downloadable URL directly into Google Drive "
            "using chunked resumable upload — zero full-file disk footprint."
        ),
        lifespan=lifespan,
    )

    is_wildcard = "*" in settings.ALLOWED_ORIGINS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=not is_wildcard,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.get("/health", tags=["meta"], include_in_schema=False)
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    return app


app = create_app()
