"""
API routers for Vibe-Quality-Searcharr.

This module exports all API routers for registration with FastAPI.
"""

from vibe_quality_searcharr.api.auth import router as auth_router
from vibe_quality_searcharr.api.instances import router as instances_router
from vibe_quality_searcharr.api.search_history import router as search_history_router
from vibe_quality_searcharr.api.search_queue import router as search_queue_router

__all__ = [
    "auth_router",
    "instances_router",
    "search_queue_router",
    "search_history_router",
]
