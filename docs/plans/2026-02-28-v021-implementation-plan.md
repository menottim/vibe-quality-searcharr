# v0.2.1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship v0.2.1 with health monitoring, queue cloning/presets, config export/integrity check, and enhanced dashboard polling.

**Architecture:** Four independent PRs, each merged to main in order. No stacking. Each PR is self-contained with tests, implementation, and template changes. Health monitoring adds a scheduler job and Instance model columns. Clone/presets is pure UI+API. Config export adds a new settings section with accordion refactor. Activity polling wires up an existing unused endpoint.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy (SQLCipher), APScheduler, Jinja2, Pico CSS, vanilla JS

**Decisions from design session:**
- Health checks: lean columns on Instance (no history table)
- Health pre-empts queues; queue 5-failure failsafe kept as safety net
- Recovery: 2 consecutive healthy checks before resuming queues
- Discord notifications on health status transitions only
- Clone: pre-fill everything in Create modal
- Presets: client-side JS, no API
- Activity: enhanced polling (not WebSocket), defer WS to v0.3.x
- Config export: DB-stored config only, export-only (defer import to future PRD item)
- Settings: accordion with `<details>` elements

**Test commands:**
```bash
.venv/bin/python -m pytest tests/unit/ --no-cov -v          # unit tests
.venv/bin/python -m pytest tests/integration/ --no-cov -v   # integration tests
.venv/bin/python -m pytest tests/ --no-cov -k "test_name"   # single test
.venv/bin/ruff check src/                                    # lint
.venv/bin/ruff format src/                                   # format
```

**Note on existing test state:** There are ~123 pre-existing test failures on main. Focus on new tests passing. Don't try to fix pre-existing failures.

---

## PR 1: Health Monitoring & Auto-Recovery

**Branch:** `feat/health-monitoring`
**Scope:** Instance model changes, health check service, scheduler integration, auto-pause/resume, Discord notifications, dashboard updates

### Task 1: Add health columns to Instance model

**Files:**
- Modify: `src/splintarr/models/instance.py`
- Test: `tests/unit/test_instance_model.py` (create new)

**Step 1: Write failing tests for new Instance columns and methods**

Create `tests/unit/test_instance_model.py`:

```python
"""Tests for Instance model health monitoring columns and methods."""

from datetime import datetime, timedelta

import pytest

from splintarr.models.instance import Instance


class TestInstanceHealthColumns:
    """Test new health monitoring columns on Instance model."""

    def test_consecutive_failures_defaults_to_zero(self, db_session):
        instance = Instance(
            user_id=1,
            name="Test Sonarr",
            instance_type="sonarr",
            url="http://sonarr:8989",
            api_key="encrypted_key",
        )
        db_session.add(instance)
        db_session.commit()
        db_session.refresh(instance)
        assert instance.consecutive_failures == 0

    def test_consecutive_successes_defaults_to_zero(self, db_session):
        instance = Instance(
            user_id=1,
            name="Test Sonarr",
            instance_type="sonarr",
            url="http://sonarr:8989",
            api_key="encrypted_key",
        )
        db_session.add(instance)
        db_session.commit()
        db_session.refresh(instance)
        assert instance.consecutive_successes == 0

    def test_last_healthy_at_defaults_to_none(self, db_session):
        instance = Instance(
            user_id=1,
            name="Test Sonarr",
            instance_type="sonarr",
            url="http://sonarr:8989",
            api_key="encrypted_key",
        )
        db_session.add(instance)
        db_session.commit()
        db_session.refresh(instance)
        assert instance.last_healthy_at is None

    def test_response_time_ms_defaults_to_none(self, db_session):
        instance = Instance(
            user_id=1,
            name="Test Sonarr",
            instance_type="sonarr",
            url="http://sonarr:8989",
            api_key="encrypted_key",
        )
        db_session.add(instance)
        db_session.commit()
        db_session.refresh(instance)
        assert instance.response_time_ms is None


class TestInstanceMarkHealthy:
    """Test mark_healthy() updates all relevant fields."""

    def test_mark_healthy_resets_failures(self, db_session):
        instance = Instance(
            user_id=1,
            name="Test",
            instance_type="sonarr",
            url="http://sonarr:8989",
            api_key="key",
            consecutive_failures=3,
        )
        db_session.add(instance)
        db_session.commit()

        instance.mark_healthy(response_time_ms=150)
        db_session.commit()
        db_session.refresh(instance)

        assert instance.consecutive_failures == 0
        assert instance.last_connection_success is True
        assert instance.connection_error is None
        assert instance.response_time_ms == 150
        assert instance.last_healthy_at is not None

    def test_mark_healthy_increments_consecutive_successes(self, db_session):
        instance = Instance(
            user_id=1,
            name="Test",
            instance_type="sonarr",
            url="http://sonarr:8989",
            api_key="key",
            consecutive_successes=1,
        )
        db_session.add(instance)
        db_session.commit()

        instance.mark_healthy(response_time_ms=100)
        db_session.commit()
        db_session.refresh(instance)

        assert instance.consecutive_successes == 2


class TestInstanceMarkUnhealthy:
    """Test mark_unhealthy() increments failure counter."""

    def test_mark_unhealthy_increments_failures(self, db_session):
        instance = Instance(
            user_id=1,
            name="Test",
            instance_type="sonarr",
            url="http://sonarr:8989",
            api_key="key",
        )
        db_session.add(instance)
        db_session.commit()

        instance.mark_unhealthy("Connection refused")
        db_session.commit()
        db_session.refresh(instance)

        assert instance.consecutive_failures == 1
        assert instance.consecutive_successes == 0
        assert instance.connection_error == "Connection refused"
        assert instance.last_connection_success is False

    def test_mark_unhealthy_resets_consecutive_successes(self, db_session):
        instance = Instance(
            user_id=1,
            name="Test",
            instance_type="sonarr",
            url="http://sonarr:8989",
            api_key="key",
            consecutive_successes=2,
        )
        db_session.add(instance)
        db_session.commit()

        instance.mark_unhealthy("Timeout")
        db_session.commit()
        db_session.refresh(instance)

        assert instance.consecutive_successes == 0


class TestInstanceConnectionStatus:
    """Test connection_status property with new states."""

    def test_connection_status_degraded_when_recovering(self, db_session):
        """Instance with 1 success after failures shows 'recovering'."""
        instance = Instance(
            user_id=1,
            name="Test",
            instance_type="sonarr",
            url="http://sonarr:8989",
            api_key="key",
        )
        db_session.add(instance)
        db_session.commit()

        # Was unhealthy, now has 1 success but needs 2
        instance.last_connection_success = True
        instance.last_connection_test = datetime.utcnow()
        instance.consecutive_successes = 1
        instance.consecutive_failures = 0

        # Still "healthy" in connection_status since last check passed
        # The "recovering" concept lives in the health check service logic,
        # not in the model property
        assert instance.connection_status == "healthy"
```

**Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/unit/test_instance_model.py --no-cov -v
```

Expected: FAIL — `consecutive_failures`, `consecutive_successes`, `last_healthy_at`, `response_time_ms` columns don't exist; `mark_healthy()` doesn't accept `response_time_ms` parameter.

**Step 3: Add columns and update methods on Instance model**

Modify `src/splintarr/models/instance.py`:

Add these columns after `connection_error`:

```python
    # Health monitoring (v0.2.1)
    consecutive_failures = Column(Integer, default=0, nullable=False)
    consecutive_successes = Column(Integer, default=0, nullable=False)
    last_healthy_at = Column(DateTime, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
```

Replace the existing `mark_healthy`, `mark_unhealthy`, and `record_connection_test` methods:

```python
    def record_connection_test(
        self, success: bool, error: str | None = None, response_time_ms: int | None = None
    ) -> None:
        """Record the result of a connection test."""
        self.last_connection_test = datetime.utcnow()
        self.last_connection_success = success
        self.connection_error = error if not success else None
        self.response_time_ms = response_time_ms

    def mark_healthy(self, response_time_ms: int | None = None) -> None:
        """Mark instance as healthy after a successful connection test."""
        self.record_connection_test(success=True, response_time_ms=response_time_ms)
        self.consecutive_failures = 0
        self.consecutive_successes = (self.consecutive_successes or 0) + 1
        self.last_healthy_at = datetime.utcnow()

    def mark_unhealthy(self, error: str) -> None:
        """Mark instance as unhealthy after a failed connection test."""
        self.record_connection_test(success=False, error=error)
        self.consecutive_failures = (self.consecutive_failures or 0) + 1
        self.consecutive_successes = 0
```

**Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/unit/test_instance_model.py --no-cov -v
```

Expected: PASS

**Step 5: Lint and commit**

```bash
.venv/bin/ruff check src/splintarr/models/instance.py --fix
.venv/bin/ruff format src/splintarr/models/instance.py
git add src/splintarr/models/instance.py tests/unit/test_instance_model.py
git commit -m "feat: add health monitoring columns and methods to Instance model"
```

---

### Task 2: Add health check interval to config

**Files:**
- Modify: `src/splintarr/config.py`

**Step 1: Add setting**

Add to the `Settings` class in `config.py`, near the existing `LIBRARY_SYNC_INTERVAL_HOURS`:

```python
    # Health monitoring
    HEALTH_CHECK_INTERVAL_MINUTES: int = 5
    HEALTH_CHECK_RECOVERY_THRESHOLD: int = 2
```

**Step 2: Commit**

```bash
git add src/splintarr/config.py
git commit -m "feat: add health check configuration settings"
```

---

### Task 3: Create HealthCheckService

**Files:**
- Create: `src/splintarr/services/health_check.py`
- Test: `tests/unit/test_health_check_service.py` (create new)

**Step 1: Write failing tests**

Create `tests/unit/test_health_check_service.py`:

```python
"""Tests for HealthCheckService."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from splintarr.models.instance import Instance
from splintarr.models.search_queue import SearchQueue
from splintarr.models.user import User
from splintarr.core.security import hash_password


@pytest.fixture
def health_user(db_session):
    user = User(
        username="healthtest",
        password_hash=hash_password("TestP@ssw0rd123!"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def healthy_instance(db_session, health_user):
    instance = Instance(
        user_id=health_user.id,
        name="Sonarr Test",
        instance_type="sonarr",
        url="http://sonarr:8989",
        api_key="encrypted_key",
        is_active=True,
        last_connection_success=True,
        consecutive_failures=0,
    )
    db_session.add(instance)
    db_session.commit()
    db_session.refresh(instance)
    return instance


@pytest.fixture
def unhealthy_instance(db_session, health_user):
    instance = Instance(
        user_id=health_user.id,
        name="Radarr Down",
        instance_type="radarr",
        url="http://radarr:7878",
        api_key="encrypted_key",
        is_active=True,
        last_connection_success=False,
        consecutive_failures=3,
        connection_error="Connection refused",
    )
    db_session.add(instance)
    db_session.commit()
    db_session.refresh(instance)
    return instance


class TestHealthCheckDetectsUnhealthy:
    """Health check detects when a healthy instance goes down."""

    @pytest.mark.asyncio
    async def test_marks_instance_unhealthy_on_failure(self, db_session, healthy_instance):
        from splintarr.services.health_check import HealthCheckService

        service = HealthCheckService(db_session)

        with patch("splintarr.services.health_check.decrypt_api_key", return_value="api_key"):
            with patch("splintarr.services.health_check.SonarrClient") as MockClient:
                mock_client = AsyncMock()
                mock_client.test_connection.return_value = {
                    "success": False,
                    "error": "Connection refused",
                    "version": None,
                    "response_time_ms": None,
                }
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_client

                result = await service.check_instance(healthy_instance)

        db_session.refresh(healthy_instance)
        assert healthy_instance.last_connection_success is False
        assert healthy_instance.consecutive_failures == 1
        assert result["status_changed"] is True
        assert result["new_status"] == "unhealthy"


class TestHealthCheckDetectsRecovery:
    """Health check detects when an unhealthy instance comes back."""

    @pytest.mark.asyncio
    async def test_marks_instance_healthy_on_success(self, db_session, unhealthy_instance):
        from splintarr.services.health_check import HealthCheckService

        service = HealthCheckService(db_session)

        with patch("splintarr.services.health_check.decrypt_api_key", return_value="api_key"):
            with patch("splintarr.services.health_check.RadarrClient") as MockClient:
                mock_client = AsyncMock()
                mock_client.test_connection.return_value = {
                    "success": True,
                    "error": None,
                    "version": "5.0.0",
                    "response_time_ms": 120,
                }
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_client

                result = await service.check_instance(unhealthy_instance)

        db_session.refresh(unhealthy_instance)
        assert unhealthy_instance.last_connection_success is True
        assert unhealthy_instance.consecutive_failures == 0
        assert unhealthy_instance.consecutive_successes == 1
        assert result["status_changed"] is False  # needs 2 successes to count as recovered


class TestAutoResumeQueues:
    """Queues auto-resume after recovery threshold met."""

    @pytest.mark.asyncio
    async def test_resumes_queues_after_recovery_threshold(
        self, db_session, unhealthy_instance
    ):
        from splintarr.services.health_check import HealthCheckService

        # Set instance to 1 consecutive success (needs 2 to resume)
        unhealthy_instance.consecutive_successes = 1
        db_session.commit()

        # Create a paused queue for this instance
        queue = SearchQueue(
            instance_id=unhealthy_instance.id,
            name="Paused Queue",
            strategy="missing",
            is_active=False,
            status="pending",
            error_message="Paused: instance unhealthy",
        )
        db_session.add(queue)
        db_session.commit()
        db_session.refresh(queue)

        service = HealthCheckService(db_session)

        with patch("splintarr.services.health_check.decrypt_api_key", return_value="key"):
            with patch("splintarr.services.health_check.RadarrClient") as MockClient:
                mock_client = AsyncMock()
                mock_client.test_connection.return_value = {
                    "success": True,
                    "error": None,
                    "version": "5.0.0",
                    "response_time_ms": 100,
                }
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_client

                result = await service.check_instance(unhealthy_instance)

        db_session.refresh(unhealthy_instance)
        db_session.refresh(queue)

        assert unhealthy_instance.consecutive_successes == 2
        assert result["queues_resumed"] == 1


class TestAutoPauseQueues:
    """Queues auto-pause when instance becomes unhealthy."""

    @pytest.mark.asyncio
    async def test_pauses_active_queues_on_first_failure(
        self, db_session, healthy_instance
    ):
        from splintarr.services.health_check import HealthCheckService

        queue = SearchQueue(
            instance_id=healthy_instance.id,
            name="Active Queue",
            strategy="missing",
            is_active=True,
            status="pending",
        )
        db_session.add(queue)
        db_session.commit()

        service = HealthCheckService(db_session)

        with patch("splintarr.services.health_check.decrypt_api_key", return_value="key"):
            with patch("splintarr.services.health_check.SonarrClient") as MockClient:
                mock_client = AsyncMock()
                mock_client.test_connection.return_value = {
                    "success": False,
                    "error": "Connection refused",
                    "version": None,
                    "response_time_ms": None,
                }
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_client

                result = await service.check_instance(healthy_instance)

        db_session.refresh(queue)
        assert queue.is_active is False
        assert "instance unhealthy" in (queue.error_message or "").lower()
        assert result["queues_paused"] == 1
```

**Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/unit/test_health_check_service.py --no-cov -v
```

Expected: FAIL — `splintarr.services.health_check` doesn't exist.

**Step 3: Implement HealthCheckService**

Create `src/splintarr/services/health_check.py`:

```python
"""Health check service for monitoring Sonarr/Radarr instance connectivity."""

import structlog
from sqlalchemy.orm import Session

from splintarr.config import settings
from splintarr.core.security import decrypt_api_key
from splintarr.models.instance import Instance
from splintarr.models.search_queue import SearchQueue
from splintarr.services.radarr import RadarrClient
from splintarr.services.sonarr import SonarrClient

logger = structlog.get_logger()


class HealthCheckService:
    """Checks instance connectivity and manages queue pause/resume."""

    def __init__(self, db: Session) -> None:
        self.db = db

    async def check_instance(self, instance: Instance) -> dict:
        """Check a single instance's health and manage queue state.

        Returns a dict with check results and any actions taken.
        """
        old_healthy = instance.is_healthy()

        # Run connectivity check
        try:
            api_key = decrypt_api_key(instance.api_key)
            client_cls = SonarrClient if instance.instance_type == "sonarr" else RadarrClient

            async with client_cls(
                url=instance.url,
                api_key=api_key,
                verify_ssl=instance.verify_ssl,
                rate_limit_per_second=instance.rate_limit_per_second or 5,
            ) as client:
                test_result = await client.test_connection()
        except Exception as e:
            logger.warning(
                "instance_health_check_client_error",
                instance_id=instance.id,
                instance_name=instance.name,
                error=str(e),
            )
            test_result = {
                "success": False,
                "error": str(e),
                "version": None,
                "response_time_ms": None,
            }

        # Update instance state
        result = {
            "instance_id": instance.id,
            "instance_name": instance.name,
            "success": test_result["success"],
            "response_time_ms": test_result.get("response_time_ms"),
            "error": test_result.get("error"),
            "status_changed": False,
            "old_status": "healthy" if old_healthy else "unhealthy",
            "new_status": "",
            "queues_paused": 0,
            "queues_resumed": 0,
        }

        if test_result["success"]:
            instance.mark_healthy(response_time_ms=test_result.get("response_time_ms"))
            result["new_status"] = "healthy"

            # Check recovery threshold
            if not old_healthy and instance.consecutive_successes >= settings.HEALTH_CHECK_RECOVERY_THRESHOLD:
                result["status_changed"] = True
                result["queues_resumed"] = self._resume_queues(instance)
                logger.info(
                    "instance_health_recovered",
                    instance_id=instance.id,
                    instance_name=instance.name,
                    consecutive_successes=instance.consecutive_successes,
                    queues_resumed=result["queues_resumed"],
                )
            elif not old_healthy:
                logger.debug(
                    "instance_health_recovering",
                    instance_id=instance.id,
                    instance_name=instance.name,
                    consecutive_successes=instance.consecutive_successes,
                    threshold=settings.HEALTH_CHECK_RECOVERY_THRESHOLD,
                )
        else:
            instance.mark_unhealthy(test_result["error"])
            result["new_status"] = "unhealthy"

            if old_healthy:
                result["status_changed"] = True
                result["queues_paused"] = self._pause_queues(instance)
                logger.warning(
                    "instance_health_status_changed",
                    instance_id=instance.id,
                    instance_name=instance.name,
                    old_status="healthy",
                    new_status="unhealthy",
                    error=test_result["error"],
                    queues_paused=result["queues_paused"],
                )
            else:
                logger.debug(
                    "instance_health_still_unhealthy",
                    instance_id=instance.id,
                    instance_name=instance.name,
                    consecutive_failures=instance.consecutive_failures,
                )

        self.db.commit()
        return result

    async def check_all_instances(self) -> list[dict]:
        """Check all active instances and return results."""
        instances = (
            self.db.query(Instance)
            .filter(Instance.is_active == True)  # noqa: E712
            .all()
        )

        if not instances:
            logger.debug("instance_health_check_no_instances")
            return []

        logger.info("instance_health_check_started", instance_count=len(instances))
        results = []

        for instance in instances:
            try:
                result = await self.check_instance(instance)
                results.append(result)
            except Exception as e:
                logger.error(
                    "instance_health_check_failed",
                    instance_id=instance.id,
                    instance_name=instance.name,
                    error=str(e),
                )

        healthy = sum(1 for r in results if r["success"])
        unhealthy = len(results) - healthy
        logger.info(
            "instance_health_check_completed",
            total=len(results),
            healthy_count=healthy,
            unhealthy_count=unhealthy,
        )

        return results

    def _pause_queues(self, instance: Instance) -> int:
        """Pause all active queues for an unhealthy instance."""
        queues = (
            self.db.query(SearchQueue)
            .filter(
                SearchQueue.instance_id == instance.id,
                SearchQueue.is_active == True,  # noqa: E712
            )
            .all()
        )

        count = 0
        for queue in queues:
            queue.is_active = False
            queue.error_message = f"Paused: instance '{instance.name}' unhealthy"
            count += 1
            logger.info(
                "search_queue_auto_paused",
                queue_id=queue.id,
                queue_name=queue.name,
                instance_id=instance.id,
                instance_name=instance.name,
            )

        return count

    def _resume_queues(self, instance: Instance) -> int:
        """Resume queues that were paused due to instance health."""
        queues = (
            self.db.query(SearchQueue)
            .filter(
                SearchQueue.instance_id == instance.id,
                SearchQueue.is_active == False,  # noqa: E712
                SearchQueue.error_message.like("%instance%unhealthy%"),
            )
            .all()
        )

        count = 0
        for queue in queues:
            queue.is_active = True
            queue.error_message = None
            queue.consecutive_failures = 0
            count += 1
            logger.info(
                "search_queue_auto_resumed",
                queue_id=queue.id,
                queue_name=queue.name,
                instance_id=instance.id,
                instance_name=instance.name,
            )

        return count
```

**Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/unit/test_health_check_service.py --no-cov -v
```

Expected: PASS

**Step 5: Lint and commit**

```bash
.venv/bin/ruff check src/splintarr/services/health_check.py --fix
.venv/bin/ruff format src/splintarr/services/health_check.py
git add src/splintarr/services/health_check.py tests/unit/test_health_check_service.py
git commit -m "feat: add HealthCheckService with auto-pause/resume queue logic"
```

---

### Task 4: Register health check job in scheduler

**Files:**
- Modify: `src/splintarr/services/scheduler.py`

**Step 1: Add health check job to scheduler start()**

In `scheduler.py`, import the health check service and add the job registration in `start()`, after `self.scheduler.start()`:

```python
# At top of file, add import:
from splintarr.services.health_check import HealthCheckService

# In start(), after self.scheduler.start() and before _load_existing_queues():
        # Register health check job
        self.scheduler.add_job(
            self._execute_health_check,
            trigger="interval",
            minutes=settings.HEALTH_CHECK_INTERVAL_MINUTES,
            id="instance_health_check",
            replace_existing=True,
            next_run_time=datetime.utcnow(),
        )
        logger.info(
            "health_check_job_registered",
            interval_minutes=settings.HEALTH_CHECK_INTERVAL_MINUTES,
        )
```

Add the job execution method on `SearchScheduler`:

```python
    async def _execute_health_check(self) -> None:
        """Execute periodic health check for all instances."""
        db = self.db_session_factory()
        try:
            service = HealthCheckService(db)
            results = await service.check_all_instances()

            # Send Discord notifications for status transitions
            for result in results:
                if result["status_changed"]:
                    await self._notify_health_change(db, result)
        except Exception as e:
            logger.error("health_check_execution_failed", error=str(e))
        finally:
            db.close()

    async def _notify_health_change(self, db: Session, result: dict) -> None:
        """Send Discord notification for health status change."""
        try:
            from splintarr.models.notification import NotificationConfig
            from splintarr.services.discord import DiscordNotificationService
            from splintarr.core.security import decrypt_field

            config = db.query(NotificationConfig).filter(
                NotificationConfig.is_active == True,  # noqa: E712
            ).first()

            if not config or not config.is_event_enabled("instance_health"):
                return

            webhook_url = decrypt_field(config.webhook_url)
            discord = DiscordNotificationService(webhook_url)

            is_healthy = result["new_status"] == "healthy"
            await discord.send_instance_health(
                instance_name=result["instance_name"],
                healthy=is_healthy,
                error=result.get("error"),
            )
        except Exception as e:
            logger.warning("health_check_notification_failed", error=str(e))
```

**Step 2: Commit**

```bash
git add src/splintarr/services/scheduler.py
git commit -m "feat: register periodic health check job in scheduler"
```

---

### Task 5: Update dashboard system-status endpoint and template

**Files:**
- Modify: `src/splintarr/api/dashboard.py` (system-status endpoint)
- Modify: `src/splintarr/templates/dashboard/index.html` (system status panel + polling)
- Modify: `src/splintarr/templates/dashboard/instances.html` (instance cards)

**Step 1: Update system-status endpoint to include new fields**

In `dashboard.py`, update the `api_dashboard_system_status` endpoint to include `consecutive_failures`, `response_time_ms`, and `connection_error`:

```python
    instance_status = [
        {
            "id": inst.id,
            "name": inst.name,
            "instance_type": inst.instance_type,
            "url": inst.sanitized_url,
            "connection_status": inst.connection_status,
            "last_connection_test": (
                inst.last_connection_test.isoformat() if inst.last_connection_test else None
            ),
            "consecutive_failures": inst.consecutive_failures,
            "response_time_ms": inst.response_time_ms,
            "connection_error": inst.connection_error,
        }
        for inst in instances
    ]
```

**Step 2: Update dashboard template system status panel**

In `dashboard/index.html`, update `buildStatusRow(inst)` to show response time and error tooltip:

After the existing `checked` span, add response time display:
```javascript
if (inst.response_time_ms !== null && inst.response_time_ms !== undefined && inst.connection_status === 'healthy') {
    var latency = document.createElement('small');
    latency.style.cssText = 'color: var(--muted-color); margin-left: 0.25rem;';
    latency.textContent = inst.response_time_ms + 'ms';
    row.appendChild(latency);
}
```

Add error display for unhealthy instances:
```javascript
if (inst.connection_status === 'unhealthy' && inst.connection_error) {
    dot.title = 'Unhealthy: ' + inst.connection_error;
}
if (inst.consecutive_failures > 0) {
    dot.title += ' (failed ' + inst.consecutive_failures + 'x)';
}
```

**Step 3: Update instances.html to show health details**

In `dashboard/instances.html`, add response time and error to the instance card `<dl>`:

After the existing Status `<dd>`, add:
```html
{% if instance.response_time_ms is not none and instance.is_healthy() %}
<dt>Response Time</dt>
<dd>{{ instance.response_time_ms }}ms</dd>
{% endif %}
{% if instance.connection_error %}
<dt>Last Error</dt>
<dd><small style="color: var(--del-color);">{{ instance.connection_error }}</small></dd>
{% endif %}
```

**Step 4: Reduce system status poll interval from 60s to 30s**

In `dashboard/index.html`, change the system status `setInterval` from `60000` to `30000`.

**Step 5: Commit**

```bash
git add src/splintarr/api/dashboard.py src/splintarr/templates/dashboard/index.html src/splintarr/templates/dashboard/instances.html
git commit -m "feat: show health check details in dashboard and instance cards"
```

---

### Task 6: Final lint, test, and PR

**Step 1: Run all tests and lint**

```bash
.venv/bin/ruff check src/ --fix
.venv/bin/ruff format src/
.venv/bin/python -m pytest tests/unit/test_instance_model.py tests/unit/test_health_check_service.py --no-cov -v
```

**Step 2: Push and create PR**

```bash
git push -u origin feat/health-monitoring
gh pr create --title "feat: health monitoring & auto-recovery" --body "$(cat <<'EOF'
## Summary
- Add periodic health checks for Sonarr/Radarr instances (default every 5 min)
- Auto-pause queues when instance becomes unreachable
- Auto-resume queues after 2 consecutive healthy checks (configurable)
- Discord notifications on health status transitions
- Dashboard shows response time, error details, failure count per instance

## Data model changes
- `Instance.consecutive_failures` (int, default 0)
- `Instance.consecutive_successes` (int, default 0)
- `Instance.last_healthy_at` (datetime, nullable)
- `Instance.response_time_ms` (int, nullable)

## Config additions
- `HEALTH_CHECK_INTERVAL_MINUTES` (default 5)
- `HEALTH_CHECK_RECOVERY_THRESHOLD` (default 2)

## Test plan
- [ ] Unit tests for Instance model health methods
- [ ] Unit tests for HealthCheckService (pause/resume/transition detection)
- [ ] Manual: stop a Sonarr container, verify dashboard shows unhealthy + queues pause
- [ ] Manual: restart Sonarr, verify recovery after 2 checks + queues resume
- [ ] Manual: verify Discord notification on health transition

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## PR 2: Clone Queue & Presets

**Branch:** `feat/clone-queue-presets`
**Scope:** Clone API endpoint, clone button UI, preset definitions, preset dropdown in Create modal

### Task 7: Add clone queue API endpoint

**Files:**
- Modify: `src/splintarr/api/search_queue.py`
- Test: `tests/unit/test_clone_queue.py` (create new)

**Step 1: Write failing test**

Create `tests/unit/test_clone_queue.py`:

```python
"""Tests for queue cloning."""

import pytest
from unittest.mock import patch, AsyncMock

from splintarr.core.security import hash_password
from splintarr.models.instance import Instance
from splintarr.models.search_queue import SearchQueue
from splintarr.models.user import User


@pytest.fixture
def clone_user(db_session):
    user = User(
        username="clonetest",
        password_hash=hash_password("TestP@ssw0rd123!"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def clone_instance(db_session, clone_user):
    instance = Instance(
        user_id=clone_user.id,
        name="Sonarr",
        instance_type="sonarr",
        url="http://sonarr:8989",
        api_key="encrypted_key",
        is_active=True,
    )
    db_session.add(instance)
    db_session.commit()
    db_session.refresh(instance)
    return instance


@pytest.fixture
def source_queue(db_session, clone_instance):
    queue = SearchQueue(
        instance_id=clone_instance.id,
        name="Missing - Sonarr",
        strategy="missing",
        is_recurring=True,
        interval_hours=4,
        is_active=True,
        status="pending",
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    return queue


class TestCloneQueueEndpoint:
    """Test POST /api/search-queues/{queue_id}/clone."""

    def test_clone_creates_new_queue_with_same_settings(
        self, client, clone_user, clone_instance, source_queue
    ):
        from splintarr.core.auth import create_access_token

        token = create_access_token(clone_user.id, clone_user.username)
        client.cookies.set("access_token", token)

        with patch("splintarr.api.search_queue.get_scheduler") as mock_sched:
            mock_sched.return_value = AsyncMock()

            response = client.post(f"/api/search-queues/{source_queue.id}/clone")

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Missing - Sonarr (copy)"
        assert data["strategy"] == "missing"
        assert data["is_recurring"] is True
        assert data["interval_hours"] == 4

    def test_clone_nonexistent_queue_returns_404(self, client, clone_user):
        from splintarr.core.auth import create_access_token

        token = create_access_token(clone_user.id, clone_user.username)
        client.cookies.set("access_token", token)

        response = client.post("/api/search-queues/9999/clone")
        assert response.status_code == 404
```

**Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/unit/test_clone_queue.py --no-cov -v
```

**Step 3: Add clone endpoint to search_queue.py**

Add to `src/splintarr/api/search_queue.py`:

```python
@router.post("/{queue_id}/clone", response_model=SearchQueueResponse, status_code=201)
@limiter.limit("10/minute")
async def clone_search_queue(
    request: Request,
    queue_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SearchQueueResponse:
    """Clone an existing search queue with the same settings."""
    source = db.query(SearchQueue).filter(SearchQueue.id == queue_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Queue not found")

    # Verify ownership via instance
    instance = db.query(Instance).filter(
        Instance.id == source.instance_id,
        Instance.user_id == current_user.id,
    ).first()
    if not instance:
        raise HTTPException(status_code=403, detail="Not authorized")

    clone = SearchQueue(
        instance_id=source.instance_id,
        name=f"{source.name} (copy)",
        strategy=source.strategy,
        is_recurring=source.is_recurring,
        interval_hours=source.interval_hours,
        filters=source.filters,
        status="pending",
        is_active=True,
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)

    # Schedule if recurring
    if clone.is_recurring and clone.is_active:
        try:
            scheduler = get_scheduler(None)
            await scheduler.schedule_queue(clone.id)
        except Exception as e:
            logger.warning("clone_queue_schedule_failed", queue_id=clone.id, error=str(e))

    logger.info(
        "search_queue_cloned",
        source_queue_id=source.id,
        new_queue_id=clone.id,
        queue_name=clone.name,
    )

    return queue_to_response(clone)
```

**Step 4: Run tests, lint, commit**

```bash
.venv/bin/python -m pytest tests/unit/test_clone_queue.py --no-cov -v
.venv/bin/ruff check src/splintarr/api/search_queue.py --fix
git add src/splintarr/api/search_queue.py tests/unit/test_clone_queue.py
git commit -m "feat: add clone queue API endpoint"
```

---

### Task 8: Add clone button and presets to queue template

**Files:**
- Modify: `src/splintarr/templates/dashboard/search_queues.html`

**Step 1: Add clone button to queue card footer**

In each queue card's `<footer>` div, add before the View button:

```html
<button class="secondary" data-action="clone-queue" data-id="{{ queue.id }}">Clone</button>
```

**Step 2: Add preset dropdown to Create Queue modal**

At the top of the Create Queue form (before the instance select), add:

```html
<label>
    Start from preset <small>(optional)</small>
    <select id="presetSelect" onchange="applyPreset(this.value)">
        <option value="">— Custom —</option>
        <option value="aggressive-missing">Aggressive Missing (hourly)</option>
        <option value="weekly-cutoff">Weekly Cutoff Unmet</option>
        <option value="new-releases">New Releases (every 4h)</option>
    </select>
</label>
```

**Step 3: Add clone and preset JavaScript**

In `{% block extra_scripts %}`, add:

```javascript
var PRESETS = {
    'aggressive-missing': {
        strategy: 'missing',
        recurring: true,
        interval_hours: 1,
        nameSuffix: 'Aggressive Missing'
    },
    'weekly-cutoff': {
        strategy: 'cutoff_unmet',
        recurring: true,
        interval_hours: 168,
        nameSuffix: 'Weekly Cutoff Unmet'
    },
    'new-releases': {
        strategy: 'recent',
        recurring: true,
        interval_hours: 4,
        nameSuffix: 'New Releases'
    }
};

function applyPreset(presetKey) {
    if (!presetKey) return;
    var preset = PRESETS[presetKey];
    if (!preset) return;

    document.getElementById('strategy').value = preset.strategy;

    var recurringCheckbox = document.getElementById('recurring');
    recurringCheckbox.checked = preset.recurring;
    toggleRecurring();

    if (preset.interval_hours) {
        document.getElementById('interval_hours').value = preset.interval_hours;
    }

    nameManuallyEdited = false;
    updateSuggestedName();
}

async function cloneQueue(queueId) {
    var result = await Splintarr.apiCall('/api/search-queues/' + queueId);
    if (!result.success) {
        Splintarr.showNotification('Failed to load queue: ' + result.error);
        return;
    }

    var queue = result.data;
    document.getElementById('presetSelect').value = '';
    document.getElementById('instance_id').value = queue.instance_id;
    document.getElementById('strategy').value = queue.strategy;

    var recurringCheckbox = document.getElementById('recurring');
    recurringCheckbox.checked = queue.is_recurring;
    toggleRecurring();

    if (queue.interval_hours) {
        document.getElementById('interval_hours').value = queue.interval_hours;
    }

    document.getElementById('name').value = queue.name + ' (copy)';
    nameManuallyEdited = true;

    document.getElementById('create-queue').showModal();
}
```

Add the clone action handler to the existing `document.addEventListener('click', ...)`:

```javascript
else if (action === 'clone-queue') cloneQueue(parseInt(target.dataset.id));
```

**Step 4: Fix Quick Actions styling (UX polish)**

In `dashboard/index.html`, find the "Browse Library" link in Quick Actions and ensure it uses the same `role="button"` or anchor styling as other action links.

**Step 5: Commit, push, PR**

```bash
git add src/splintarr/templates/dashboard/search_queues.html src/splintarr/templates/dashboard/index.html
git commit -m "feat: add clone button and presets dropdown to queue UI"
git push -u origin feat/clone-queue-presets
gh pr create --title "feat: clone queue & presets" --body "$(cat <<'EOF'
## Summary
- Clone button on queue cards — opens Create modal pre-filled with source queue settings
- Preset dropdown in Create Queue modal: Aggressive Missing, Weekly Cutoff Unmet, New Releases
- POST /api/search-queues/{id}/clone API endpoint
- UX: Quick Actions styling consistency

## Test plan
- [ ] Clone a queue, verify modal pre-fills correctly
- [ ] Change instance on cloned queue, verify creates new queue
- [ ] Select each preset, verify form fields update
- [ ] Override preset fields, verify custom values are used
- [ ] Clone non-existent queue returns 404

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## PR 3: Config Export & Integrity Check

**Branch:** `feat/config-export-integrity`
**Scope:** Export endpoint, integrity check endpoint, new System settings section, accordion refactor, UX polish

### Task 9: Add config export and integrity check endpoints

**Files:**
- Create: `src/splintarr/api/config.py`
- Modify: `src/splintarr/main.py` (register router)
- Test: `tests/unit/test_config_export.py` (create new)

**Step 1: Write failing tests**

Create `tests/unit/test_config_export.py`:

```python
"""Tests for config export and integrity check."""

import pytest
from unittest.mock import patch

from splintarr.core.security import hash_password, encrypt_field
from splintarr.models.instance import Instance
from splintarr.models.search_queue import SearchQueue
from splintarr.models.user import User


@pytest.fixture
def export_user(db_session):
    user = User(
        username="exporttest",
        password_hash=hash_password("TestP@ssw0rd123!"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def export_instance(db_session, export_user):
    instance = Instance(
        user_id=export_user.id,
        name="Sonarr",
        instance_type="sonarr",
        url="http://sonarr:8989",
        api_key=encrypt_field("my-secret-api-key"),
        is_active=True,
    )
    db_session.add(instance)
    db_session.commit()
    db_session.refresh(instance)
    return instance


class TestConfigExport:
    """Test GET /api/config/export."""

    def test_export_includes_instances_without_api_keys(
        self, client, export_user, export_instance
    ):
        from splintarr.core.auth import create_access_token

        token = create_access_token(export_user.id, export_user.username)
        client.cookies.set("access_token", token)

        response = client.get("/api/config/export")
        assert response.status_code == 200
        data = response.json()

        assert "instances" in data
        assert len(data["instances"]) == 1
        assert data["instances"][0]["name"] == "Sonarr"
        assert data["instances"][0]["api_key"] == "[REDACTED]"

    def test_export_includes_version(self, client, export_user):
        from splintarr.core.auth import create_access_token

        token = create_access_token(export_user.id, export_user.username)
        client.cookies.set("access_token", token)

        response = client.get("/api/config/export")
        assert response.status_code == 200
        data = response.json()
        assert "splintarr_version" in data
        assert "exported_at" in data


class TestIntegrityCheck:
    """Test POST /api/config/integrity-check."""

    def test_integrity_check_returns_ok(self, client, export_user):
        from splintarr.core.auth import create_access_token

        token = create_access_token(export_user.id, export_user.username)
        client.cookies.set("access_token", token)

        response = client.post("/api/config/integrity-check")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
```

**Step 2: Run tests — verify they fail**

```bash
.venv/bin/python -m pytest tests/unit/test_config_export.py --no-cov -v
```

**Step 3: Implement config router**

Create `src/splintarr/api/config.py`:

```python
"""Config export and database integrity check endpoints."""

from datetime import datetime, timezone
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from sqlalchemy import text
from sqlalchemy.orm import Session

from splintarr.config import settings
from splintarr.core.auth import get_current_user_from_cookie
from splintarr.core.rate_limit import rate_limit_key_func
from splintarr.database import get_db, get_engine
from splintarr.models.exclusion import SearchExclusion
from splintarr.models.instance import Instance
from splintarr.models.notification import NotificationConfig
from splintarr.models.search_queue import SearchQueue
from splintarr.models.user import User

logger = structlog.get_logger()
router = APIRouter(prefix="/api/config", tags=["config"])
limiter = Limiter(key_func=rate_limit_key_func)


@router.get("/export", include_in_schema=False)
@limiter.limit("5/minute")
async def export_config(
    request: Request,
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Export DB-stored configuration as JSON. API keys and webhook URLs are redacted."""
    instances = (
        db.query(Instance)
        .filter(Instance.user_id == current_user.id)
        .all()
    )
    queues = (
        db.query(SearchQueue)
        .join(Instance)
        .filter(Instance.user_id == current_user.id)
        .all()
    )
    exclusions = (
        db.query(SearchExclusion)
        .filter(SearchExclusion.user_id == current_user.id)
        .all()
    )
    notification = (
        db.query(NotificationConfig)
        .filter(NotificationConfig.user_id == current_user.id)
        .first()
    )

    export_data: dict[str, Any] = {
        "splintarr_version": settings.APP_NAME if hasattr(settings, "APP_NAME") else "splintarr",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "instances": [
            {
                "name": inst.name,
                "instance_type": inst.instance_type,
                "url": inst.sanitized_url,
                "api_key": "[REDACTED]",
                "verify_ssl": inst.verify_ssl,
                "timeout_seconds": inst.timeout_seconds,
                "rate_limit_per_second": inst.rate_limit_per_second,
            }
            for inst in instances
        ],
        "search_queues": [
            {
                "name": q.name,
                "instance_id": q.instance_id,
                "strategy": q.strategy,
                "is_recurring": q.is_recurring,
                "interval_hours": q.interval_hours,
                "filters": q.filters,
                "is_active": q.is_active,
            }
            for q in queues
        ],
        "exclusions": [
            {
                "title": exc.title,
                "content_type": exc.content_type,
                "external_id": exc.external_id,
                "reason": exc.reason,
                "expires_at": exc.expires_at.isoformat() if exc.expires_at else None,
            }
            for exc in exclusions
        ],
    }

    if notification:
        export_data["notification_config"] = {
            "webhook_url": "[REDACTED]",
            "events_enabled": notification.get_events(),
            "is_active": notification.is_active,
        }

    logger.info("config_exported", user_id=current_user.id)

    headers = {
        "Content-Disposition": f'attachment; filename="splintarr-config-{datetime.now().strftime("%Y%m%d")}.json"'
    }
    return JSONResponse(content=export_data, headers=headers)


@router.post("/integrity-check", include_in_schema=False)
@limiter.limit("5/minute")
async def check_database_integrity(
    request: Request,
    current_user: User = Depends(get_current_user_from_cookie),
) -> JSONResponse:
    """Run PRAGMA integrity_check on the database."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA integrity_check"))
            rows = result.fetchall()

        if rows and rows[0][0] == "ok":
            logger.info("database_integrity_check_passed", user_id=current_user.id)
            return JSONResponse(content={"status": "ok", "details": ["ok"]})
        else:
            details = [row[0] for row in rows]
            logger.warning(
                "database_integrity_check_issues",
                user_id=current_user.id,
                issues=details,
            )
            return JSONResponse(
                content={"status": "error", "details": details},
                status_code=200,
            )
    except Exception as e:
        logger.error("database_integrity_check_failed", error=str(e))
        return JSONResponse(
            content={"status": "error", "details": [str(e)]},
            status_code=500,
        )
```

Register in `main.py` — add `from splintarr.api import config` to imports, then `app.include_router(config.router)`.

**Step 4: Run tests, lint, commit**

```bash
.venv/bin/python -m pytest tests/unit/test_config_export.py --no-cov -v
.venv/bin/ruff check src/splintarr/api/config.py --fix
git add src/splintarr/api/config.py src/splintarr/main.py tests/unit/test_config_export.py
git commit -m "feat: add config export and database integrity check endpoints"
```

---

### Task 10: Settings page accordion refactor + System section

**Files:**
- Modify: `src/splintarr/templates/dashboard/settings.html`

**Step 1: Refactor to accordion layout**

Wrap each existing `<article>` in a `<details>` element. Account Information gets `open` attribute. Add new System section before Danger Zone.

The new System section:

```html
<details>
    <summary><strong>System</strong></summary>
    <article>
        <h4>Config Export</h4>
        <p>Download your configuration (instances, queues, exclusions, notification settings) as JSON. API keys and webhook URLs are redacted.</p>
        <button id="exportConfigBtn" class="secondary">Download Config Export</button>

        <hr>

        <h4>Database Integrity</h4>
        <p>Run a database integrity check to verify your data is not corrupted.</p>
        <div style="display: flex; gap: 0.5rem; align-items: center;">
            <button id="integrityCheckBtn" class="secondary">Run Integrity Check</button>
            <small id="integrityResult" style="display: none;"></small>
        </div>
    </article>
</details>
```

**Step 2: Add System section JavaScript**

```javascript
document.getElementById('exportConfigBtn').addEventListener('click', async function() {
    this.setAttribute('aria-busy', 'true');
    try {
        var response = await fetch('/api/config/export');
        if (!response.ok) throw new Error('Export failed');
        var blob = await response.blob();
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'splintarr-config-' + new Date().toISOString().slice(0, 10) + '.json';
        a.click();
        URL.revokeObjectURL(url);
    } catch (err) {
        Splintarr.showNotification('Export failed: ' + err.message);
    } finally {
        this.removeAttribute('aria-busy');
    }
});

document.getElementById('integrityCheckBtn').addEventListener('click', async function() {
    this.setAttribute('aria-busy', 'true');
    var resultEl = document.getElementById('integrityResult');
    resultEl.style.display = 'none';
    try {
        var response = await fetch('/api/config/integrity-check', { method: 'POST' });
        var data = await response.json();
        resultEl.style.display = 'inline';
        if (data.status === 'ok') {
            resultEl.style.color = 'var(--ins-color)';
            resultEl.textContent = '✓ Database integrity OK';
        } else {
            resultEl.style.color = 'var(--del-color)';
            resultEl.textContent = '✗ Issues found: ' + data.details.join(', ');
        }
    } catch (err) {
        resultEl.style.display = 'inline';
        resultEl.style.color = 'var(--del-color)';
        resultEl.textContent = '✗ Check failed: ' + err.message;
    } finally {
        this.removeAttribute('aria-busy');
    }
});
```

**Step 3: UX polish — replace alert() with showNotification()**

In the same template, replace all `alert(...)` calls with `Splintarr.showNotification(message, type)`:
- Change Password success: `Splintarr.showNotification('Password changed successfully', 'success')`
- 2FA enable/disable: replace `alert()` with `Splintarr.showNotification()`
- Logout All: replace `alert()` with `Splintarr.showNotification()`

**Step 4: UX polish — notification save feedback**

Add `aria-busy` attribute handling on the notification Save button:
```javascript
// Before fetch:
saveBtn.setAttribute('aria-busy', 'true');
saveBtn.disabled = true;
// After fetch (success or error):
saveBtn.removeAttribute('aria-busy');
saveBtn.disabled = false;
```

**Step 5: Commit, push, PR**

```bash
git add src/splintarr/templates/dashboard/settings.html
git commit -m "feat: config export, integrity check, settings accordion, UX polish"
git push -u origin feat/config-export-integrity
gh pr create --title "feat: config export & integrity check" --body "$(cat <<'EOF'
## Summary
- Config export: download instances, queues, exclusions, notification config as JSON (API keys redacted)
- Database integrity check: run PRAGMA integrity_check from settings page
- Settings page refactored to accordion layout with <details> elements
- New "System" section in settings for export + integrity check
- UX: replaced alert() with toast notifications throughout settings
- UX: loading state on notification save button

## Test plan
- [ ] Download config export, verify JSON structure and redacted secrets
- [ ] Run integrity check, verify "OK" result
- [ ] Verify accordion sections open/close correctly
- [ ] Verify toast notifications replace browser alerts
- [ ] Verify notification save button shows loading state

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## PR 4: Enhanced Activity Polling

**Branch:** `feat/enhanced-activity-polling`
**Scope:** Wire up activity endpoint, live-update activity table, clear filters buttons

### Task 11: Wire up activity polling on dashboard

**Files:**
- Modify: `src/splintarr/templates/dashboard/index.html`

**Step 1: Add activity polling loop**

In `{% block extra_scripts %}`, add a new polling loop after the existing stats and system-status loops:

```javascript
// Activity feed — poll every 15s
async function refreshActivity() {
    try {
        var response = await fetch('/api/dashboard/activity?limit=10');
        if (!response.ok) return;
        var data = await response.json();
        updateActivityTable(data.activity);
    } catch (e) {
        // silent fail — table keeps last known state
    }
}

function updateActivityTable(activities) {
    var tbody = document.getElementById('activity-tbody');
    if (!tbody || !activities) return;

    tbody.replaceChildren();

    if (activities.length === 0) {
        var emptyRow = document.createElement('tr');
        var emptyCell = document.createElement('td');
        emptyCell.colSpan = 5;
        emptyCell.style.textAlign = 'center';
        emptyCell.style.color = 'var(--muted-color)';
        emptyCell.textContent = 'No recent activity';
        emptyRow.appendChild(emptyCell);
        tbody.appendChild(emptyRow);
        return;
    }

    activities.forEach(function(item) {
        var row = document.createElement('tr');

        // Instance
        var instCell = document.createElement('td');
        instCell.textContent = item.instance_name || '—';
        row.appendChild(instCell);

        // Strategy
        var stratCell = document.createElement('td');
        var stratCode = document.createElement('code');
        stratCode.textContent = item.strategy;
        stratCell.appendChild(stratCode);
        row.appendChild(stratCell);

        // Status
        var statusCell = document.createElement('td');
        if (item.status === 'success') {
            statusCell.style.color = 'var(--ins-color)';
            statusCell.textContent = '\u2713 Completed';
        } else if (item.status === 'failed') {
            statusCell.style.color = 'var(--del-color)';
            statusCell.textContent = '\u2717 Failed';
        } else if (item.status === 'in_progress') {
            statusCell.style.color = 'var(--primary)';
            statusCell.textContent = '\u27f3 Running';
        } else {
            statusCell.textContent = item.status;
        }
        row.appendChild(statusCell);

        // Items
        var itemsCell = document.createElement('td');
        itemsCell.textContent = item.items_searched + ' searched \u00b7 ' + item.items_found + ' found';
        row.appendChild(itemsCell);

        // Time
        var timeCell = document.createElement('td');
        if (item.started_at) {
            timeCell.textContent = Splintarr.formatTimeAgo(new Date(item.started_at));
        }
        row.appendChild(timeCell);

        tbody.appendChild(row);
    });
}

setInterval(refreshActivity, 15000);
refreshActivity(); // also run once on load
```

**Step 2: Add id to activity table tbody**

In the server-rendered activity table, add `id="activity-tbody"` to the `<tbody>` element so the JS can target it.

**Step 3: Commit**

```bash
git add src/splintarr/templates/dashboard/index.html
git commit -m "feat: wire up activity polling to live-update dashboard table"
```

---

### Task 12: Add clear filters to Library and Exclusions

**Files:**
- Modify: `src/splintarr/templates/components/library_filters.html` (if exists) or `src/splintarr/templates/dashboard/library.html`
- Modify: `src/splintarr/templates/dashboard/exclusions.html`

**Step 1: Add "Clear filters" link**

For each filter form, add a link that resets to the base URL:

```html
{% if request.query_string %}
<a href="{{ request.path }}" style="margin-left: 0.5rem; font-size: 0.875rem;">Clear filters</a>
{% endif %}
```

Place this next to the filter submit button or after the filter `<select>` elements.

**Step 2: Commit, push, PR**

```bash
git add src/splintarr/templates/
git commit -m "feat: add clear filters and enhanced activity polling"
git push -u origin feat/enhanced-activity-polling
gh pr create --title "feat: enhanced activity polling & UX polish" --body "$(cat <<'EOF'
## Summary
- Dashboard activity table now live-updates every 15s via /api/dashboard/activity
- System status polling reduced from 60s to 30s
- Clear filters link on Library and Exclusions pages
- Activity table rebuilds via JS DOM manipulation (same pattern as system status)

## Test plan
- [ ] Dashboard activity table updates without page refresh
- [ ] Verify table shows correct status colors and formatting
- [ ] Trigger a search, verify it appears in table within 15s
- [ ] Click "Clear filters" on Library page, verify resets to unfiltered view
- [ ] Click "Clear filters" on Exclusions page, verify same

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Post-Implementation: PRD Update

After all 4 PRs are merged:

1. Update `docs/PRD.md` Feature Status table — mark Features 3, 4, 5, 6 as **Done**
2. Update Feature 5 description to note "Enhanced polling (WebSocket deferred to v0.3.x)"
3. Add "Config Import" as a deferred future item (per design decision)
4. Add to Document History: "v0.2.1 shipped: Health Monitoring, Clone/Presets, Config Export, Activity Polling"
5. Bump version to `0.2.1` in `pyproject.toml`

---

## Dependency Graph

```
PR 1 (Health Monitoring)  ──→  merge to main
                                    │
PR 2 (Clone/Presets)  ─────→  merge to main  (independent of PR 1)
                                    │
PR 3 (Config/Integrity)  ──→  merge to main  (independent of PR 1, 2)
                                    │
PR 4 (Activity Polling)  ──→  merge to main  (independent of PR 1, 2, 3)
                                    │
                              PRD update + version bump
```

All 4 PRs are independent and can be worked on in parallel or in any order. The recommended order (PR 1→2→3→4) is by priority, not by dependency.
