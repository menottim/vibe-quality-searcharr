"""
Integration tests for custom strategy filters through the API.

Tests verify that custom strategy filters work end-to-end:
- Queue creation with custom strategy saves filters correctly (DB round-trip)
- Non-custom strategy rejects filters (422 validation error via API)
- Custom strategy without filters is rejected (422 validation error via API)
"""

import json

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from splintarr.api.auth import get_current_user
from splintarr.core.auth import get_current_user_from_cookie
from splintarr.models import Instance, SearchQueue, User


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user in the database."""
    user = User(
        username="customfilteruser",
        password_hash="fakehash",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_instance(db_session: Session, test_user: User) -> Instance:
    """Create a test Sonarr instance owned by the test user."""
    instance = Instance(
        user_id=test_user.id,
        name="Test Sonarr",
        instance_type="sonarr",
        url="https://sonarr.example.com",
        api_key="encrypted_fake_key",
        is_active=True,
    )
    db_session.add(instance)
    db_session.commit()
    db_session.refresh(instance)
    return instance


@pytest.fixture
def authed_client(client: TestClient, test_user: User) -> TestClient:
    """Authenticated test client with auth dependency overridden."""
    from splintarr.main import app

    app.dependency_overrides[get_current_user_from_cookie] = lambda: test_user
    app.dependency_overrides[get_current_user] = lambda: test_user
    yield client
    # client fixture teardown calls app.dependency_overrides.clear()


class TestCustomStrategyQueueCreation:
    """Test creating search queues with custom strategy and filters.

    These tests verify the full DB round-trip: creating a SearchQueue with
    custom strategy and JSON-serialized filters, then reading them back.
    They bypass the HTTP layer to avoid in-memory DB pool conflicts during
    lifespan startup, but test the same schema validation and serialization
    code that the API endpoint uses.
    """

    def test_create_queue_with_custom_strategy_saves_filters(
        self, db_session: Session, test_instance: Instance
    ):
        """Custom strategy with full filters saves correctly to DB as JSON."""
        from splintarr.schemas.search import CustomFilterConfig, SearchQueueCreate

        # Validate through Pydantic schema (same as endpoint)
        queue_data = SearchQueueCreate(
            instance_id=test_instance.id,
            name="Custom Filtered Search",
            strategy="custom",
            filters=CustomFilterConfig(
                sources=["missing", "cutoff_unmet"],
                year_min=2000,
                year_max=2025,
                quality_profiles=["HD-1080p"],
                statuses=["continuing"],
            ),
        )

        # Serialize filters to JSON (same as endpoint does)
        filters_json = (
            json.dumps(queue_data.filters.model_dump())
            if queue_data.filters is not None
            else None
        )

        queue = SearchQueue(
            instance_id=queue_data.instance_id,
            name=queue_data.name,
            strategy=queue_data.strategy,
            is_recurring=queue_data.recurring,
            interval_hours=queue_data.interval_hours,
            filters=filters_json,
            cooldown_mode=queue_data.cooldown_mode,
            cooldown_hours=queue_data.cooldown_hours,
            max_items_per_run=queue_data.max_items_per_run,
            status="pending",
            is_active=True,
        )
        queue.schedule_next_run(delay_hours=0)

        db_session.add(queue)
        db_session.commit()
        db_session.refresh(queue)

        assert queue.id is not None
        assert queue.strategy == "custom"
        assert queue.name == "Custom Filtered Search"
        assert queue.is_active is True

        # Read back from DB and verify filters round-trip
        loaded = db_session.query(SearchQueue).filter_by(id=queue.id).first()
        assert loaded is not None
        assert loaded.filters is not None
        parsed = json.loads(loaded.filters)

        assert "missing" in parsed["sources"]
        assert "cutoff_unmet" in parsed["sources"]
        assert parsed["year_min"] == 2000
        assert parsed["year_max"] == 2025
        assert "HD-1080p" in parsed["quality_profiles"]
        assert "continuing" in parsed["statuses"]

    def test_create_queue_with_custom_strategy_minimal_filters(
        self, db_session: Session, test_instance: Instance
    ):
        """Custom strategy with only required filter fields (sources) persists correctly."""
        from splintarr.schemas.search import CustomFilterConfig, SearchQueueCreate

        queue_data = SearchQueueCreate(
            instance_id=test_instance.id,
            name="Minimal Custom Search",
            strategy="custom",
            filters=CustomFilterConfig(sources=["missing"]),
        )

        filters_json = (
            json.dumps(queue_data.filters.model_dump())
            if queue_data.filters is not None
            else None
        )

        queue = SearchQueue(
            instance_id=queue_data.instance_id,
            name=queue_data.name,
            strategy=queue_data.strategy,
            is_recurring=False,
            filters=filters_json,
            status="pending",
            is_active=True,
        )

        db_session.add(queue)
        db_session.commit()
        db_session.refresh(queue)

        loaded = db_session.query(SearchQueue).filter_by(id=queue.id).first()
        assert loaded is not None
        parsed = json.loads(loaded.filters)
        assert parsed["sources"] == ["missing"]
        assert parsed.get("year_min") is None
        assert parsed.get("year_max") is None
        # Optional list fields default to empty
        assert parsed.get("quality_profiles") == []

    def test_filters_none_for_non_custom_strategy(
        self, db_session: Session, test_instance: Instance
    ):
        """Non-custom strategy stores filters as None."""
        queue = SearchQueue(
            instance_id=test_instance.id,
            name="Missing Strategy Queue",
            strategy="missing",
            is_recurring=False,
            filters=None,
            status="pending",
            is_active=True,
        )

        db_session.add(queue)
        db_session.commit()
        db_session.refresh(queue)

        loaded = db_session.query(SearchQueue).filter_by(id=queue.id).first()
        assert loaded is not None
        assert loaded.filters is None
        assert loaded.strategy == "missing"


class TestNonCustomStrategyRejectsFilters:
    """Test that non-custom strategies reject filters via API validation."""

    def test_missing_strategy_with_filters_rejected(
        self, authed_client: TestClient, test_instance: Instance
    ):
        """POST with strategy=missing and filters set returns 422."""
        payload = {
            "instance_id": test_instance.id,
            "name": "Missing With Filters",
            "strategy": "missing",
            "filters": {
                "sources": ["missing"],
            },
        }

        response = authed_client.post("/api/search-queues", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_cutoff_unmet_strategy_with_filters_rejected(
        self, authed_client: TestClient, test_instance: Instance
    ):
        """POST with strategy=cutoff_unmet and filters set returns 422."""
        payload = {
            "instance_id": test_instance.id,
            "name": "Cutoff With Filters",
            "strategy": "cutoff_unmet",
            "filters": {
                "sources": ["cutoff_unmet"],
            },
        }

        response = authed_client.post("/api/search-queues", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_recent_strategy_with_filters_rejected(
        self, authed_client: TestClient, test_instance: Instance
    ):
        """POST with strategy=recent and filters set returns 422."""
        payload = {
            "instance_id": test_instance.id,
            "name": "Recent With Filters",
            "strategy": "recent",
            "filters": {
                "sources": ["missing"],
            },
        }

        response = authed_client.post("/api/search-queues", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestCustomStrategyRequiresFilters:
    """Test that custom strategy requires filters."""

    def test_custom_strategy_without_filters_rejected(
        self, authed_client: TestClient, test_instance: Instance
    ):
        """POST with strategy=custom and no filters returns 422."""
        payload = {
            "instance_id": test_instance.id,
            "name": "Custom No Filters",
            "strategy": "custom",
            # No filters field
        }

        response = authed_client.post("/api/search-queues", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_custom_strategy_with_null_filters_rejected(
        self, authed_client: TestClient, test_instance: Instance
    ):
        """POST with strategy=custom and filters=null returns 422."""
        payload = {
            "instance_id": test_instance.id,
            "name": "Custom Null Filters",
            "strategy": "custom",
            "filters": None,
        }

        response = authed_client.post("/api/search-queues", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_custom_strategy_with_empty_sources_rejected(
        self, authed_client: TestClient, test_instance: Instance
    ):
        """POST with strategy=custom and empty sources list returns 422."""
        payload = {
            "instance_id": test_instance.id,
            "name": "Custom Empty Sources",
            "strategy": "custom",
            "filters": {
                "sources": [],
            },
        }

        response = authed_client.post("/api/search-queues", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_custom_strategy_with_invalid_year_range_rejected(
        self, authed_client: TestClient, test_instance: Instance
    ):
        """POST with strategy=custom and year_min > year_max returns 422."""
        payload = {
            "instance_id": test_instance.id,
            "name": "Custom Bad Years",
            "strategy": "custom",
            "filters": {
                "sources": ["missing"],
                "year_min": 2025,
                "year_max": 2000,
            },
        }

        response = authed_client.post("/api/search-queues", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestCustomFilterSchemaValidation:
    """Test CustomFilterConfig and SearchQueueCreate schema validation."""

    def test_schema_rejects_non_custom_with_filters(self):
        """SearchQueueCreate model validator rejects filters on non-custom strategy."""
        from pydantic import ValidationError

        from splintarr.schemas.search import CustomFilterConfig, SearchQueueCreate

        with pytest.raises(ValidationError, match="Filters only allowed with custom strategy"):
            SearchQueueCreate(
                instance_id=1,
                name="Bad Queue",
                strategy="missing",
                filters=CustomFilterConfig(sources=["missing"]),
            )

    def test_schema_rejects_custom_without_filters(self):
        """SearchQueueCreate model validator rejects custom strategy without filters."""
        from pydantic import ValidationError

        from splintarr.schemas.search import SearchQueueCreate

        with pytest.raises(ValidationError, match="Custom strategy requires filters"):
            SearchQueueCreate(
                instance_id=1,
                name="Bad Queue",
                strategy="custom",
            )

    def test_schema_rejects_invalid_year_range(self):
        """CustomFilterConfig rejects year_min > year_max."""
        from pydantic import ValidationError

        from splintarr.schemas.search import CustomFilterConfig

        with pytest.raises(ValidationError, match="year_min must be <= year_max"):
            CustomFilterConfig(
                sources=["missing"],
                year_min=2025,
                year_max=2000,
            )

    def test_schema_rejects_empty_sources(self):
        """CustomFilterConfig requires at least one source."""
        from pydantic import ValidationError

        from splintarr.schemas.search import CustomFilterConfig

        with pytest.raises(ValidationError):
            CustomFilterConfig(sources=[])

    def test_schema_accepts_valid_custom_config(self):
        """SearchQueueCreate accepts valid custom strategy with filters."""
        from splintarr.schemas.search import CustomFilterConfig, SearchQueueCreate

        queue = SearchQueueCreate(
            instance_id=1,
            name="Valid Custom Queue",
            strategy="custom",
            filters=CustomFilterConfig(
                sources=["missing", "cutoff_unmet"],
                year_min=2000,
                year_max=2025,
                quality_profiles=["HD-1080p"],
                statuses=["continuing"],
            ),
        )

        assert queue.strategy == "custom"
        assert queue.filters is not None
        assert queue.filters.sources == ["missing", "cutoff_unmet"]
        assert queue.filters.year_min == 2000
        assert queue.filters.year_max == 2025

    def test_filters_model_dump_is_json_serializable(self):
        """CustomFilterConfig.model_dump() produces JSON-serializable dict."""
        from splintarr.schemas.search import CustomFilterConfig

        config = CustomFilterConfig(
            sources=["missing"],
            year_min=2010,
            quality_profiles=["HD-1080p", "HDTV-720p"],
            statuses=["continuing", "ended"],
        )

        dumped = config.model_dump()
        json_str = json.dumps(dumped)
        parsed = json.loads(json_str)

        assert parsed["sources"] == ["missing"]
        assert parsed["year_min"] == 2010
        assert parsed["year_max"] is None
        assert parsed["quality_profiles"] == ["HD-1080p", "HDTV-720p"]
        assert parsed["statuses"] == ["continuing", "ended"]
