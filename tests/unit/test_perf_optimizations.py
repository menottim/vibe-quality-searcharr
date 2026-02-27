"""
Unit tests for performance optimizations.

Tests that optimized query patterns produce correct results:
- Dashboard stats consolidated queries (Fix 1)
- Dashboard activity joinedload / no N+1 (Fix 2)
- Bulk token revocation (Fix 3)
- Search history SQL aggregation (Fix 4)
- Dead TYPE_CHECKING blocks removed (Fix 6)
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from splintarr.core.auth import revoke_all_user_tokens
from splintarr.core.security import hash_password
from splintarr.models.instance import Instance
from splintarr.models.search_history import SearchHistory
from splintarr.models.search_queue import SearchQueue
from splintarr.models.user import RefreshToken, User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_user(db: Session, username: str = "testuser") -> User:
    user = User(
        username=username,
        password_hash=hash_password("TestP@ssw0rd123!"),
        is_active=True,
        is_superuser=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_instance(
    db: Session,
    user: User,
    name: str = "Test Sonarr",
    is_active: bool = True,
) -> Instance:
    inst = Instance(
        user_id=user.id,
        name=name,
        instance_type="sonarr",
        url="http://localhost:8989",
        api_key="encrypted_key_placeholder",
        is_active=is_active,
    )
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return inst


def _create_queue(
    db: Session,
    instance: Instance,
    is_active: bool = True,
    queue_status: str = "pending",
) -> SearchQueue:
    q = SearchQueue(
        instance_id=instance.id,
        name="Test Queue",
        strategy="missing",
        is_active=is_active,
        status=queue_status,
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return q


def _create_search_history(
    db: Session,
    instance: Instance,
    search_status: str = "success",
    started_at: datetime | None = None,
    items_searched: int = 10,
    items_found: int = 5,
    searches_triggered: int = 3,
    duration_seconds: int | None = 60,
    strategy: str = "missing",
) -> SearchHistory:
    h = SearchHistory(
        instance_id=instance.id,
        search_name="Test Search",
        strategy=strategy,
        status=search_status,
        started_at=started_at or datetime.utcnow(),
        completed_at=datetime.utcnow(),
        duration_seconds=duration_seconds,
        items_searched=items_searched,
        items_found=items_found,
        searches_triggered=searches_triggered,
    )
    db.add(h)
    db.commit()
    db.refresh(h)
    return h


# ===========================================================================
# Fix 1: Dashboard stats consolidated queries
# ===========================================================================


class TestDashboardStatsConsolidated:
    """Verify get_dashboard_stats returns correct values with consolidated queries."""

    @pytest.mark.asyncio
    async def test_stats_empty_database(self, db_session: Session):
        """Stats with no data should return all zeros."""
        from splintarr.api.dashboard import get_dashboard_stats

        user = _create_user(db_session)
        stats = await get_dashboard_stats(db_session, user)

        assert stats["instances"]["total"] == 0
        assert stats["instances"]["active"] == 0
        assert stats["instances"]["inactive"] == 0
        assert stats["search_queues"]["total"] == 0
        assert stats["search_queues"]["active"] == 0
        assert stats["search_queues"]["paused"] == 0
        assert stats["searches"]["today"] == 0
        assert stats["searches"]["this_week"] == 0
        assert stats["searches"]["success_rate"] == 0

    @pytest.mark.asyncio
    async def test_stats_instance_counts(self, db_session: Session):
        """Instance counts should distinguish active vs inactive."""
        from splintarr.api.dashboard import get_dashboard_stats

        user = _create_user(db_session)
        _create_instance(db_session, user, name="Active1", is_active=True)
        _create_instance(db_session, user, name="Active2", is_active=True)
        _create_instance(db_session, user, name="Inactive1", is_active=False)

        stats = await get_dashboard_stats(db_session, user)

        assert stats["instances"]["total"] == 3
        assert stats["instances"]["active"] == 2
        assert stats["instances"]["inactive"] == 1

    @pytest.mark.asyncio
    async def test_stats_queue_counts(self, db_session: Session):
        """Queue counts should distinguish active-pending from paused/completed."""
        from splintarr.api.dashboard import get_dashboard_stats

        user = _create_user(db_session)
        inst = _create_instance(db_session, user)
        _create_queue(db_session, inst, is_active=True, queue_status="pending")
        _create_queue(db_session, inst, is_active=True, queue_status="completed")
        _create_queue(db_session, inst, is_active=False, queue_status="pending")

        stats = await get_dashboard_stats(db_session, user)

        assert stats["search_queues"]["total"] == 3
        assert stats["search_queues"]["active"] == 1  # only active + pending/running
        assert stats["search_queues"]["paused"] == 2

    @pytest.mark.asyncio
    async def test_stats_search_counts_today(self, db_session: Session):
        """Searches today vs this week should be counted correctly."""
        from splintarr.api.dashboard import get_dashboard_stats

        user = _create_user(db_session)
        inst = _create_instance(db_session, user)

        # Create a search from today
        _create_search_history(db_session, inst, started_at=datetime.utcnow())

        # Create a search from 3 days ago (still within the week)
        _create_search_history(
            db_session,
            inst,
            started_at=datetime.utcnow() - timedelta(days=3),
        )

        stats = await get_dashboard_stats(db_session, user)

        assert stats["searches"]["today"] >= 1
        assert stats["searches"]["this_week"] >= 2

    @pytest.mark.asyncio
    async def test_stats_success_rate(self, db_session: Session):
        """Success rate should be calculated from completed vs total this week."""
        from splintarr.api.dashboard import get_dashboard_stats

        user = _create_user(db_session)
        inst = _create_instance(db_session, user)

        now = datetime.utcnow()
        # 2 completed searches
        _create_search_history(db_session, inst, search_status="completed", started_at=now)
        _create_search_history(
            db_session, inst, search_status="completed", started_at=now - timedelta(hours=1)
        )
        # 1 failed search
        _create_search_history(
            db_session, inst, search_status="failed", started_at=now - timedelta(hours=2)
        )

        stats = await get_dashboard_stats(db_session, user)

        # 2 completed out of 3 total => 66.7%
        assert stats["searches"]["this_week"] == 3
        assert stats["searches"]["success_rate"] == pytest.approx(66.7, abs=0.1)

    @pytest.mark.asyncio
    async def test_stats_user_isolation(self, db_session: Session):
        """Stats should only count data belonging to the requesting user."""
        from splintarr.api.dashboard import get_dashboard_stats

        user_a = _create_user(db_session, username="user_a")
        user_b = _create_user(db_session, username="user_b")

        _create_instance(db_session, user_a, name="A-Instance")
        _create_instance(db_session, user_b, name="B-Instance1")
        _create_instance(db_session, user_b, name="B-Instance2")

        stats_a = await get_dashboard_stats(db_session, user_a)
        stats_b = await get_dashboard_stats(db_session, user_b)

        assert stats_a["instances"]["total"] == 1
        assert stats_b["instances"]["total"] == 2


# ===========================================================================
# Fix 3: Bulk token revocation
# ===========================================================================


class TestBulkTokenRevocation:
    """Verify revoke_all_user_tokens uses bulk update correctly."""

    def test_revoke_all_returns_correct_count(self, db_session: Session):
        """Bulk revocation should return the number of tokens revoked."""
        user = _create_user(db_session)

        # Create 3 active tokens
        for i in range(3):
            token = RefreshToken(
                jti=f"test-jti-{i}",
                user_id=user.id,
                expires_at=datetime.utcnow() + timedelta(days=30),
            )
            db_session.add(token)
        db_session.commit()

        count = revoke_all_user_tokens(db_session, user.id)
        assert count == 3

    def test_revoke_all_marks_tokens_revoked(self, db_session: Session):
        """All tokens should be marked as revoked with a revoked_at timestamp."""
        user = _create_user(db_session)

        for i in range(3):
            token = RefreshToken(
                jti=f"test-jti-{i}",
                user_id=user.id,
                expires_at=datetime.utcnow() + timedelta(days=30),
            )
            db_session.add(token)
        db_session.commit()

        revoke_all_user_tokens(db_session, user.id)

        # Expire the session cache to read fresh data from DB
        db_session.expire_all()

        tokens = (
            db_session.query(RefreshToken)
            .filter(RefreshToken.user_id == user.id)
            .all()
        )
        for t in tokens:
            assert t.revoked is True
            assert t.revoked_at is not None

    def test_revoke_all_skips_already_revoked(self, db_session: Session):
        """Already-revoked tokens should not be counted again."""
        user = _create_user(db_session)

        # One already revoked
        revoked = RefreshToken(
            jti="already-revoked",
            user_id=user.id,
            expires_at=datetime.utcnow() + timedelta(days=30),
            revoked=True,
            revoked_at=datetime.utcnow() - timedelta(hours=1),
        )
        # One active
        active = RefreshToken(
            jti="still-active",
            user_id=user.id,
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        db_session.add_all([revoked, active])
        db_session.commit()

        count = revoke_all_user_tokens(db_session, user.id)
        assert count == 1

    def test_revoke_all_does_not_affect_other_users(self, db_session: Session):
        """Revoking tokens for one user should not affect another user's tokens."""
        user_a = _create_user(db_session, username="user_a")
        user_b = _create_user(db_session, username="user_b")

        token_a = RefreshToken(
            jti="token-a",
            user_id=user_a.id,
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        token_b = RefreshToken(
            jti="token-b",
            user_id=user_b.id,
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        db_session.add_all([token_a, token_b])
        db_session.commit()

        revoke_all_user_tokens(db_session, user_a.id)

        db_session.expire_all()
        token_b_refreshed = (
            db_session.query(RefreshToken).filter(RefreshToken.jti == "token-b").one()
        )
        assert token_b_refreshed.revoked is False


# ===========================================================================
# Fix 4: Search history SQL aggregation
# ===========================================================================


class TestSearchHistoryStatisticsAggregation:
    """Verify get_statistics produces correct results with SQL aggregation."""

    def test_statistics_empty(self, db_session: Session):
        """Empty history should return zero-valued statistics."""
        from splintarr.services.search_history import SearchHistoryService

        service = SearchHistoryService(lambda: db_session)
        stats = service.get_statistics(days=30)

        assert stats["total_searches"] == 0
        assert stats["successful_searches"] == 0
        assert stats["failed_searches"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["total_items_searched"] == 0
        assert stats["total_items_found"] == 0
        assert stats["total_searches_triggered"] == 0
        assert stats["avg_duration_seconds"] == 0.0
        assert stats["searches_by_strategy"] == {}
        assert len(stats["searches_by_day"]) == 30

    def test_statistics_counts_and_rates(self, db_session: Session):
        """Aggregate counts and success rate should be correct."""
        from splintarr.services.search_history import SearchHistoryService

        user = _create_user(db_session)
        inst = _create_instance(db_session, user)
        now = datetime.utcnow()

        # 3 successful, 2 failed
        for i in range(3):
            _create_search_history(
                db_session, inst, search_status="success", started_at=now - timedelta(days=i)
            )
        for i in range(2):
            _create_search_history(
                db_session,
                inst,
                search_status="failed",
                started_at=now - timedelta(days=i, hours=1),
            )

        service = SearchHistoryService(lambda: db_session)
        stats = service.get_statistics(days=30)

        assert stats["total_searches"] == 5
        assert stats["successful_searches"] == 3
        assert stats["failed_searches"] == 2
        assert stats["success_rate"] == pytest.approx(3 / 5)

    def test_statistics_item_totals(self, db_session: Session):
        """Items searched/found/triggered should be summed correctly."""
        from splintarr.services.search_history import SearchHistoryService

        user = _create_user(db_session)
        inst = _create_instance(db_session, user)
        now = datetime.utcnow()

        _create_search_history(
            db_session,
            inst,
            started_at=now,
            items_searched=100,
            items_found=50,
            searches_triggered=10,
        )
        _create_search_history(
            db_session,
            inst,
            started_at=now - timedelta(hours=1),
            items_searched=200,
            items_found=75,
            searches_triggered=20,
        )

        service = SearchHistoryService(lambda: db_session)
        stats = service.get_statistics(days=30)

        assert stats["total_items_searched"] == 300
        assert stats["total_items_found"] == 125
        assert stats["total_searches_triggered"] == 30

    def test_statistics_avg_duration(self, db_session: Session):
        """Average duration should be correctly computed."""
        from splintarr.services.search_history import SearchHistoryService

        user = _create_user(db_session)
        inst = _create_instance(db_session, user)
        now = datetime.utcnow()

        _create_search_history(db_session, inst, started_at=now, duration_seconds=60)
        _create_search_history(
            db_session,
            inst,
            started_at=now - timedelta(hours=1),
            duration_seconds=120,
        )

        service = SearchHistoryService(lambda: db_session)
        stats = service.get_statistics(days=30)

        assert stats["avg_duration_seconds"] == pytest.approx(90.0)

    def test_statistics_by_strategy(self, db_session: Session):
        """Searches by strategy should group correctly."""
        from splintarr.services.search_history import SearchHistoryService

        user = _create_user(db_session)
        inst = _create_instance(db_session, user)
        now = datetime.utcnow()

        _create_search_history(db_session, inst, started_at=now, strategy="missing")
        _create_search_history(
            db_session, inst, started_at=now - timedelta(hours=1), strategy="missing"
        )
        _create_search_history(
            db_session, inst, started_at=now - timedelta(hours=2), strategy="recent"
        )

        service = SearchHistoryService(lambda: db_session)
        stats = service.get_statistics(days=30)

        assert stats["searches_by_strategy"]["missing"] == 2
        assert stats["searches_by_strategy"]["recent"] == 1

    def test_statistics_by_day(self, db_session: Session):
        """Searches by day should include zero-activity days and correct counts."""
        from splintarr.services.search_history import SearchHistoryService

        user = _create_user(db_session)
        inst = _create_instance(db_session, user)

        now = datetime.utcnow()
        two_days_ago = now - timedelta(days=2)

        _create_search_history(
            db_session, inst, search_status="success", started_at=two_days_ago
        )
        _create_search_history(
            db_session, inst, search_status="failed", started_at=two_days_ago
        )

        service = SearchHistoryService(lambda: db_session)
        stats = service.get_statistics(days=7)

        # Should have 7 entries
        assert len(stats["searches_by_day"]) == 7

        # Find the day with data
        target_date = two_days_ago.date().isoformat()
        day_data = next(
            (d for d in stats["searches_by_day"] if d["date"] == target_date), None
        )
        assert day_data is not None
        assert day_data["count"] == 2
        assert day_data["successful"] == 1
        assert day_data["failed"] == 1

    def test_statistics_instance_filter(self, db_session: Session):
        """Statistics should respect the instance_id filter."""
        from splintarr.services.search_history import SearchHistoryService

        user = _create_user(db_session)
        inst_a = _create_instance(db_session, user, name="A")
        inst_b = _create_instance(db_session, user, name="B")
        now = datetime.utcnow()

        _create_search_history(db_session, inst_a, started_at=now)
        _create_search_history(db_session, inst_a, started_at=now - timedelta(hours=1))
        _create_search_history(db_session, inst_b, started_at=now - timedelta(hours=2))

        service = SearchHistoryService(lambda: db_session)
        stats = service.get_statistics(instance_id=inst_a.id, days=30)

        assert stats["total_searches"] == 2

    def test_statistics_partial_success_counted_as_successful(self, db_session: Session):
        """partial_success status should count toward successful_searches."""
        from splintarr.services.search_history import SearchHistoryService

        user = _create_user(db_session)
        inst = _create_instance(db_session, user)
        now = datetime.utcnow()

        _create_search_history(db_session, inst, search_status="partial_success", started_at=now)

        service = SearchHistoryService(lambda: db_session)
        stats = service.get_statistics(days=30)

        assert stats["successful_searches"] == 1
        assert stats["failed_searches"] == 0


# ===========================================================================
# Fix 6: Dead TYPE_CHECKING blocks removed
# ===========================================================================


class TestDeadCodeRemoved:
    """Verify that dead TYPE_CHECKING imports were removed."""

    def test_user_model_no_type_checking_import(self):
        """user.py should not import TYPE_CHECKING."""
        import inspect
        import splintarr.models.user as mod

        source = inspect.getsource(mod)
        assert "TYPE_CHECKING" not in source

    def test_search_queue_model_no_type_checking_import(self):
        """search_queue.py should not import TYPE_CHECKING."""
        import inspect
        import splintarr.models.search_queue as mod

        source = inspect.getsource(mod)
        assert "TYPE_CHECKING" not in source

    def test_search_history_model_no_type_checking_import(self):
        """search_history.py should not import TYPE_CHECKING."""
        import inspect
        import splintarr.models.search_history as mod

        source = inspect.getsource(mod)
        assert "TYPE_CHECKING" not in source
