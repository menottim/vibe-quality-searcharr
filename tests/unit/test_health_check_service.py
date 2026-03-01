"""
Unit tests for HealthCheckService.

Tests cover:
1. Healthy instance stays healthy (no status change, no queue action)
2. Healthy instance goes unhealthy -> status_changed=True, queues paused
3. Unhealthy instance stays unhealthy (no status change, no queue action)
4. Unhealthy instance has 1 success -> recovering (not yet recovered)
5. Unhealthy instance has 2 successes -> recovered, queues resumed
6. _pause_queues only pauses active queues for the specific instance
7. _resume_queues only resumes queues with "instance unhealthy" error message
8. check_all_instances handles empty instance list gracefully
9. Client exception caught and treated as failure
"""

from unittest.mock import AsyncMock, patch

import pytest

from splintarr.core.security import hash_password
from splintarr.models.instance import Instance
from splintarr.models.search_queue import SearchQueue
from splintarr.models.user import User
from splintarr.services.health_check import HealthCheckService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user(db_session):
    """Create a test user."""
    u = User(
        username="healthtest",
        password_hash=hash_password("TestP@ssw0rd123!"),
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    return u


@pytest.fixture
def sonarr_instance(db_session, user):
    """Create a stably healthy Sonarr instance (past recovery threshold)."""
    inst = Instance(
        user_id=user.id,
        name="Sonarr",
        instance_type="sonarr",
        url="http://sonarr:8989",
        api_key="encrypted_key",
        is_active=True,
    )
    # Mark it healthy enough times to be past the recovery threshold,
    # so it is in a stable-healthy state (not recovering).
    inst.mark_healthy(response_time_ms=100)
    inst.mark_healthy(response_time_ms=100)
    db_session.add(inst)
    db_session.commit()
    return inst


@pytest.fixture
def radarr_instance(db_session, user):
    """Create a stably healthy Radarr instance (past recovery threshold)."""
    inst = Instance(
        user_id=user.id,
        name="Radarr",
        instance_type="radarr",
        url="http://radarr:7878",
        api_key="encrypted_key",
        is_active=True,
    )
    inst.mark_healthy(response_time_ms=80)
    inst.mark_healthy(response_time_ms=80)
    db_session.add(inst)
    db_session.commit()
    return inst


@pytest.fixture
def unhealthy_instance(db_session, user):
    """Create an unhealthy Sonarr instance (has been failing)."""
    inst = Instance(
        user_id=user.id,
        name="Sonarr Down",
        instance_type="sonarr",
        url="http://sonarr-down:8989",
        api_key="encrypted_key",
        is_active=True,
    )
    # Mark unhealthy so connection_status == "unhealthy"
    inst.mark_unhealthy("Connection refused")
    db_session.add(inst)
    db_session.commit()
    return inst


@pytest.fixture
def service(db_session):
    """Create a HealthCheckService."""
    return HealthCheckService(db=db_session)


def _mock_client_success(response_time_ms=120):
    """Build mock patches for a successful test_connection call."""
    mock_client = AsyncMock()
    mock_client.test_connection.return_value = {
        "success": True,
        "error": None,
        "version": "5.0.0",
        "response_time_ms": response_time_ms,
    }
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def _mock_client_failure(error_msg="Connection refused"):
    """Build mock patches for a failed test_connection call."""
    mock_client = AsyncMock()
    mock_client.test_connection.return_value = {
        "success": False,
        "error": error_msg,
        "version": None,
        "response_time_ms": None,
    }
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# ---------------------------------------------------------------------------
# 1. Healthy instance stays healthy
# ---------------------------------------------------------------------------


class TestHealthyStaysHealthy:
    """A healthy instance that passes the check remains healthy with no side effects."""

    async def test_no_status_change(self, service, sonarr_instance):
        mock_client = _mock_client_success()
        with (
            patch(
                "splintarr.services.health_check.decrypt_api_key",
                return_value="api_key",
            ),
            patch("splintarr.services.health_check.SonarrClient") as MockClient,
        ):
            MockClient.return_value = mock_client
            result = await service.check_instance(sonarr_instance)

        assert result["success"] is True
        assert result["status_changed"] is False
        assert result["old_status"] == "healthy"
        assert result["new_status"] == "healthy"
        assert result["queues_paused"] == 0
        assert result["queues_resumed"] == 0

    async def test_response_time_stored(self, service, sonarr_instance):
        mock_client = _mock_client_success(response_time_ms=250)
        with (
            patch(
                "splintarr.services.health_check.decrypt_api_key",
                return_value="api_key",
            ),
            patch("splintarr.services.health_check.SonarrClient") as MockClient,
        ):
            MockClient.return_value = mock_client
            result = await service.check_instance(sonarr_instance)

        assert result["response_time_ms"] == 250
        assert sonarr_instance.response_time_ms == 250


# ---------------------------------------------------------------------------
# 2. Healthy instance goes unhealthy
# ---------------------------------------------------------------------------


class TestHealthyGoesUnhealthy:
    """A healthy instance that fails a check transitions to unhealthy."""

    async def test_status_changed_and_queues_paused(self, service, db_session, sonarr_instance):
        # Create active queues for the instance
        q1 = SearchQueue(
            instance_id=sonarr_instance.id,
            name="Queue 1",
            strategy="missing",
            is_active=True,
        )
        q2 = SearchQueue(
            instance_id=sonarr_instance.id,
            name="Queue 2",
            strategy="cutoff_unmet",
            is_active=True,
        )
        db_session.add_all([q1, q2])
        db_session.commit()

        mock_client = _mock_client_failure("Connection refused")
        with (
            patch(
                "splintarr.services.health_check.decrypt_api_key",
                return_value="api_key",
            ),
            patch("splintarr.services.health_check.SonarrClient") as MockClient,
        ):
            MockClient.return_value = mock_client
            result = await service.check_instance(sonarr_instance)

        assert result["success"] is False
        assert result["status_changed"] is True
        assert result["old_status"] == "healthy"
        assert result["new_status"] == "unhealthy"
        assert result["queues_paused"] == 2
        assert result["error"] == "Connection refused"

        # Verify queues were actually paused
        db_session.refresh(q1)
        db_session.refresh(q2)
        assert q1.is_active is False
        assert q2.is_active is False
        assert "unhealthy" in q1.error_message
        assert "unhealthy" in q2.error_message


# ---------------------------------------------------------------------------
# 3. Unhealthy instance stays unhealthy
# ---------------------------------------------------------------------------


class TestUnhealthyStaysUnhealthy:
    """An already unhealthy instance that fails again stays unhealthy with no queue actions."""

    async def test_no_status_change(self, service, unhealthy_instance):
        mock_client = _mock_client_failure("Still down")
        with (
            patch(
                "splintarr.services.health_check.decrypt_api_key",
                return_value="api_key",
            ),
            patch("splintarr.services.health_check.SonarrClient") as MockClient,
        ):
            MockClient.return_value = mock_client
            result = await service.check_instance(unhealthy_instance)

        assert result["success"] is False
        assert result["status_changed"] is False
        assert result["old_status"] == "unhealthy"
        assert result["new_status"] == "unhealthy"
        assert result["queues_paused"] == 0
        assert result["queues_resumed"] == 0

    async def test_consecutive_failures_incremented(self, service, unhealthy_instance):
        old_failures = unhealthy_instance.consecutive_failures
        mock_client = _mock_client_failure("timeout")
        with (
            patch(
                "splintarr.services.health_check.decrypt_api_key",
                return_value="api_key",
            ),
            patch("splintarr.services.health_check.SonarrClient") as MockClient,
        ):
            MockClient.return_value = mock_client
            await service.check_instance(unhealthy_instance)

        assert unhealthy_instance.consecutive_failures == old_failures + 1


# ---------------------------------------------------------------------------
# 4. Unhealthy instance has 1 success -> recovering
# ---------------------------------------------------------------------------


class TestUnhealthyRecovering:
    """One successful check is not enough to mark recovery (threshold=2 by default)."""

    async def test_recovering_not_yet_recovered(self, service, unhealthy_instance):
        mock_client = _mock_client_success()
        with (
            patch(
                "splintarr.services.health_check.decrypt_api_key",
                return_value="api_key",
            ),
            patch("splintarr.services.health_check.SonarrClient") as MockClient,
        ):
            MockClient.return_value = mock_client
            result = await service.check_instance(unhealthy_instance)

        # Instance had consecutive_successes=0 before; now 1 after mark_healthy
        assert unhealthy_instance.consecutive_successes == 1
        assert result["success"] is True
        # Not yet recovered: threshold is 2
        assert result["status_changed"] is False
        assert result["queues_resumed"] == 0


# ---------------------------------------------------------------------------
# 5. Unhealthy instance has 2 successes -> recovered
# ---------------------------------------------------------------------------


class TestUnhealthyRecovered:
    """Two consecutive successes meet the recovery threshold; queues are resumed."""

    async def test_recovered_after_threshold(self, service, db_session, unhealthy_instance):
        # Create a queue that was paused by health monitoring
        q = SearchQueue(
            instance_id=unhealthy_instance.id,
            name="Paused Queue",
            strategy="missing",
            is_active=False,
            error_message=f"Paused: instance '{unhealthy_instance.name}' unhealthy",
        )
        db_session.add(q)
        db_session.commit()

        mock_client = _mock_client_success()

        # First success: recovering
        with (
            patch(
                "splintarr.services.health_check.decrypt_api_key",
                return_value="api_key",
            ),
            patch("splintarr.services.health_check.SonarrClient") as MockClient,
        ):
            MockClient.return_value = mock_client
            result1 = await service.check_instance(unhealthy_instance)

        assert result1["status_changed"] is False
        assert result1["queues_resumed"] == 0
        assert unhealthy_instance.consecutive_successes == 1

        # Second success: recovered
        mock_client2 = _mock_client_success()
        with (
            patch(
                "splintarr.services.health_check.decrypt_api_key",
                return_value="api_key",
            ),
            patch("splintarr.services.health_check.SonarrClient") as MockClient,
        ):
            MockClient.return_value = mock_client2
            result2 = await service.check_instance(unhealthy_instance)

        assert result2["status_changed"] is True
        assert result2["queues_resumed"] == 1
        assert result2["new_status"] == "healthy"

        # Verify queue was resumed
        db_session.refresh(q)
        assert q.is_active is True
        assert q.error_message is None
        assert q.consecutive_failures == 0


# ---------------------------------------------------------------------------
# 6. _pause_queues only pauses active queues for the specific instance
# ---------------------------------------------------------------------------


class TestPauseQueuesScoping:
    """_pause_queues only affects active queues belonging to the given instance."""

    def test_only_active_queues_for_instance(self, service, db_session, user):
        inst_a = Instance(
            user_id=user.id,
            name="Instance A",
            instance_type="sonarr",
            url="http://a:8989",
            api_key="enc",
            is_active=True,
        )
        inst_b = Instance(
            user_id=user.id,
            name="Instance B",
            instance_type="radarr",
            url="http://b:7878",
            api_key="enc",
            is_active=True,
        )
        db_session.add_all([inst_a, inst_b])
        db_session.commit()

        # Active queue for A (should be paused)
        q_a_active = SearchQueue(
            instance_id=inst_a.id,
            name="A Active",
            strategy="missing",
            is_active=True,
        )
        # Inactive queue for A (should NOT be paused)
        q_a_inactive = SearchQueue(
            instance_id=inst_a.id,
            name="A Inactive",
            strategy="missing",
            is_active=False,
        )
        # Active queue for B (should NOT be paused — wrong instance)
        q_b_active = SearchQueue(
            instance_id=inst_b.id,
            name="B Active",
            strategy="missing",
            is_active=True,
        )
        db_session.add_all([q_a_active, q_a_inactive, q_b_active])
        db_session.commit()

        paused = service._pause_queues(inst_a)

        assert paused == 1
        db_session.flush()
        db_session.refresh(q_a_active)
        db_session.refresh(q_a_inactive)
        db_session.refresh(q_b_active)

        assert q_a_active.is_active is False
        assert "unhealthy" in q_a_active.error_message
        assert q_a_inactive.is_active is False  # Was already inactive
        assert q_b_active.is_active is True  # Different instance, untouched


# ---------------------------------------------------------------------------
# 7. _resume_queues only resumes queues with "instance unhealthy" error
# ---------------------------------------------------------------------------


class TestResumeQueuesScoping:
    """_resume_queues only resumes queues paused by health monitoring."""

    def test_only_health_paused_queues_resumed(self, service, db_session, user):
        inst = Instance(
            user_id=user.id,
            name="TestInst",
            instance_type="sonarr",
            url="http://inst:8989",
            api_key="enc",
            is_active=True,
        )
        db_session.add(inst)
        db_session.commit()

        # Paused by health monitoring (should be resumed)
        q_health = SearchQueue(
            instance_id=inst.id,
            name="Health Paused",
            strategy="missing",
            is_active=False,
            error_message="Paused: instance 'TestInst' unhealthy",
        )
        # Paused manually with a different error (should NOT be resumed)
        q_manual = SearchQueue(
            instance_id=inst.id,
            name="Manually Paused",
            strategy="missing",
            is_active=False,
            error_message="Deactivated after 5 consecutive failures",
        )
        # Active queue (should NOT be touched)
        q_active = SearchQueue(
            instance_id=inst.id,
            name="Still Active",
            strategy="cutoff_unmet",
            is_active=True,
        )
        db_session.add_all([q_health, q_manual, q_active])
        db_session.commit()

        resumed = service._resume_queues(inst)

        assert resumed == 1
        db_session.flush()
        db_session.refresh(q_health)
        db_session.refresh(q_manual)
        db_session.refresh(q_active)

        assert q_health.is_active is True
        assert q_health.error_message is None
        assert q_health.consecutive_failures == 0

        assert q_manual.is_active is False  # Untouched
        assert q_manual.error_message == "Deactivated after 5 consecutive failures"

        assert q_active.is_active is True  # Untouched


# ---------------------------------------------------------------------------
# 8. check_all_instances handles empty instance list
# ---------------------------------------------------------------------------


class TestCheckAllInstances:
    """check_all_instances iterates all active instances or handles none."""

    async def test_empty_instance_list(self, service, db_session):
        # No instances in the DB
        results = await service.check_all_instances()
        assert results == []

    async def test_checks_all_active_instances(self, service, db_session, user):
        inst1 = Instance(
            user_id=user.id,
            name="Active Sonarr",
            instance_type="sonarr",
            url="http://sonarr:8989",
            api_key="enc",
            is_active=True,
        )
        inst2 = Instance(
            user_id=user.id,
            name="Active Radarr",
            instance_type="radarr",
            url="http://radarr:7878",
            api_key="enc",
            is_active=True,
        )
        inst_inactive = Instance(
            user_id=user.id,
            name="Inactive",
            instance_type="sonarr",
            url="http://off:8989",
            api_key="enc",
            is_active=False,
        )
        db_session.add_all([inst1, inst2, inst_inactive])
        db_session.commit()

        mock_client = _mock_client_success()
        with (
            patch(
                "splintarr.services.health_check.decrypt_api_key",
                return_value="api_key",
            ),
            patch("splintarr.services.health_check.SonarrClient") as MockSonarr,
            patch("splintarr.services.health_check.RadarrClient") as MockRadarr,
        ):
            MockSonarr.return_value = mock_client
            MockRadarr.return_value = mock_client
            results = await service.check_all_instances()

        assert len(results) == 2
        instance_names = {r["instance_name"] for r in results}
        assert instance_names == {"Active Sonarr", "Active Radarr"}


# ---------------------------------------------------------------------------
# 9. Client exception caught and treated as failure
# ---------------------------------------------------------------------------


class TestClientException:
    """Exceptions during client creation or test_connection are handled gracefully."""

    async def test_decrypt_exception_treated_as_failure(self, service, sonarr_instance):
        with patch(
            "splintarr.services.health_check.decrypt_api_key",
            side_effect=Exception("Decryption failed"),
        ):
            result = await service.check_instance(sonarr_instance)

        assert result["success"] is False
        assert result["status_changed"] is True  # Was healthy, now unhealthy
        assert "Decryption failed" in result["error"]

    async def test_client_exception_treated_as_failure(self, service, sonarr_instance):
        mock_client = AsyncMock()
        mock_client.test_connection.side_effect = Exception("Network error")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "splintarr.services.health_check.decrypt_api_key",
                return_value="api_key",
            ),
            patch("splintarr.services.health_check.SonarrClient") as MockClient,
        ):
            MockClient.return_value = mock_client
            result = await service.check_instance(sonarr_instance)

        assert result["success"] is False
        assert result["status_changed"] is True
        assert "Network error" in result["error"]

    async def test_radarr_client_used_for_radarr_instance(self, service, radarr_instance):
        """Verify that RadarrClient is used when instance_type is 'radarr'."""
        mock_client = _mock_client_success()
        with (
            patch(
                "splintarr.services.health_check.decrypt_api_key",
                return_value="api_key",
            ),
            patch("splintarr.services.health_check.SonarrClient") as MockSonarr,
            patch("splintarr.services.health_check.RadarrClient") as MockRadarr,
        ):
            MockRadarr.return_value = mock_client
            result = await service.check_instance(radarr_instance)

        assert result["success"] is True
        MockRadarr.assert_called_once()
        MockSonarr.assert_not_called()
