"""
app/api/v1/router.py
Mounts all v1 endpoint routers under the /api/v1 prefix.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import router as transfer_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(transfer_router, tags=["transfer"])
