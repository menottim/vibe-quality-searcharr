"""
Unit tests for GET /api/instances/{id}/quality-profiles endpoint.

Tests cover:
- Returns distinct quality profiles for a given instance
- Returns empty list when no library items exist
- Authentication required (no cookie -> 401)
- Instance not found -> 404
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from splintarr.core.auth import get_current_user_from_cookie
from splintarr.models.instance import Instance
from splintarr.models.library import LibraryItem
from splintarr.models.user import User


@pytest.fixture
def user(db_session: Session) -> User:
    """Create a test user."""
    user = User(
        username="testuser",
        password_hash="hash",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def instance(db_session: Session, user: User) -> Instance:
    """Create a test instance owned by the user."""
    inst = Instance(
        user_id=user.id,
        name="Test Sonarr",
        instance_type="sonarr",
        url="http://localhost:8989",
        api_key="encrypted-key",
        is_active=True,
    )
    db_session.add(inst)
    db_session.commit()
    db_session.refresh(inst)
    return inst


@pytest.fixture
def mock_db() -> MagicMock:
    """Create a mock DB session for endpoints."""
    return MagicMock(spec=Session)


@pytest.fixture
def authed_client(client: TestClient, user: User, mock_db: MagicMock) -> TestClient:
    """Create an authenticated test client with auth and DB dependency overrides."""
    from splintarr.database import get_db
    from splintarr.main import app

    app.dependency_overrides[get_current_user_from_cookie] = lambda: user
    app.dependency_overrides[get_db] = lambda: mock_db
    yield client


class TestGetQualityProfiles:
    """Tests for GET /api/instances/{id}/quality-profiles."""

    def test_returns_distinct_profiles(
        self, authed_client: TestClient, user: User, mock_db: MagicMock
    ):
        """Returns distinct quality profile names for instance library items."""
        # Mock the Instance query
        mock_instance = MagicMock(spec=Instance)
        mock_instance.id = 1
        mock_instance.user_id = user.id

        # Chain: db.query(Instance).filter(...).first()
        instance_query = MagicMock()
        instance_query.first.return_value = mock_instance

        # Chain: db.query(LibraryItem.quality_profile).filter(...).distinct().order_by(...).all()
        profile_query = MagicMock()
        profile_query.filter.return_value = profile_query
        profile_query.distinct.return_value = profile_query
        profile_query.order_by.return_value = profile_query
        profile_query.all.return_value = [("HD-1080p",), ("SD",), ("Ultra-HD",)]

        def query_side_effect(model):
            if model is Instance:
                q = MagicMock()
                q.filter.return_value = instance_query
                return q
            # LibraryItem.quality_profile
            return profile_query

        mock_db.query.side_effect = query_side_effect

        response = authed_client.get("/api/instances/1/quality-profiles")

        assert response.status_code == 200
        data = response.json()
        assert data["profiles"] == ["HD-1080p", "SD", "Ultra-HD"]

    def test_returns_empty_list_when_no_items(
        self, authed_client: TestClient, user: User, mock_db: MagicMock
    ):
        """Returns empty profiles list when no library items exist."""
        mock_instance = MagicMock(spec=Instance)
        mock_instance.id = 1
        mock_instance.user_id = user.id

        instance_query = MagicMock()
        instance_query.first.return_value = mock_instance

        profile_query = MagicMock()
        profile_query.filter.return_value = profile_query
        profile_query.distinct.return_value = profile_query
        profile_query.order_by.return_value = profile_query
        profile_query.all.return_value = []

        def query_side_effect(model):
            if model is Instance:
                q = MagicMock()
                q.filter.return_value = instance_query
                return q
            return profile_query

        mock_db.query.side_effect = query_side_effect

        response = authed_client.get("/api/instances/1/quality-profiles")

        assert response.status_code == 200
        data = response.json()
        assert data["profiles"] == []

    def test_instance_not_found_returns_404(
        self, authed_client: TestClient, user: User, mock_db: MagicMock
    ):
        """Returns 404 when instance doesn't exist or isn't owned by user."""
        instance_query = MagicMock()
        instance_query.first.return_value = None

        q = MagicMock()
        q.filter.return_value = instance_query
        mock_db.query.return_value = q

        response = authed_client.get("/api/instances/999/quality-profiles")

        assert response.status_code == 404
        assert response.json()["detail"] == "Instance not found"

    def test_requires_auth(self, client: TestClient):
        """Endpoint requires authentication — returns 401 without cookie."""
        response = client.get("/api/instances/1/quality-profiles")
        assert response.status_code == 401
