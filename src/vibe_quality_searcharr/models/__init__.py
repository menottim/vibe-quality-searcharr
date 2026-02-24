"""
Database models for Vibe-Quality-Searcharr.

This module exports all SQLAlchemy models for easy import throughout the application.
All models use the Base declarative base from database.py.
"""

from vibe_quality_searcharr.models.instance import Instance
from vibe_quality_searcharr.models.search_history import SearchHistory
from vibe_quality_searcharr.models.search_queue import SearchQueue
from vibe_quality_searcharr.models.user import RefreshToken, User

# Export all models
__all__ = [
    "User",
    "RefreshToken",
    "Instance",
    "SearchQueue",
    "SearchHistory",
]
