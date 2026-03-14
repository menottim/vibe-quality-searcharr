# Discord Notification "Started" Events — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add "started" Discord notifications for search queue execution and library sync, so users see when operations begin (not just when they complete).

**Architecture:** Two new methods on `DiscordNotificationService` (blue informational embeds), two new dispatch helpers that reuse existing event toggles (`search_triggered` and `library_sync`). No schema, model, or UI changes.

**Tech Stack:** Python 3.13, FastAPI, httpx, structlog, pytest-asyncio

---

### Task 1: Add `send_search_started` to Discord service

**Files:**
- Modify: `src/splintarr/services/discord.py:52-110` (insert before `send_search_summary`)
- Test: `tests/unit/test_discord_started_notifications.py` (create)

**Step 1: Write the failing tests**

Create `tests/unit/test_discord_started_notifications.py`:

```python
"""Tests for Discord 'started' notification embeds."""
import pytest
from unittest.mock import AsyncMock, patch

from splintarr.services.discord import DiscordNotificationService


class TestSendSearchStarted:
    """Test send_search_started Discord embed."""

    @pytest.mark.asyncio
    async def test_sends_blue_embed(self):
        service = DiscordNotificationService("https://discord.com/api/webhooks/test")
        with patch.object(service, "_send_embed", new_callable=AsyncMock, return_value=True) as mock:
            result = await service.send_search_started(
                search_name="Missing TV",
                instance_name="Sonarr Main",
                strategy="missing",
                estimated_items=20,
            )
            assert result is True
            embed = mock.call_args[0][0]
            assert embed["color"] == 0x3498DB  # COLOR_BLUE
            assert "Missing TV" in embed["title"]
            assert "Started" in embed["title"]

    @pytest.mark.asyncio
    async def test_embed_includes_details(self):
        service = DiscordNotificationService("https://discord.com/api/webhooks/test")
        with patch.object(service, "_send_embed", new_callable=AsyncMock, return_value=True) as mock:
            await service.send_search_started(
                search_name="Cutoff Upgrades",
                instance_name="Sonarr 4K",
                strategy="cutoff",
                estimated_items=15,
            )
            embed = mock.call_args[0][0]
            assert "Sonarr 4K" in embed["description"]
            assert "cutoff" in embed["description"]
            assert "15" in embed["description"]
            assert "footer" in embed
            assert "timestamp" in embed
```

**Step 2: Run tests to verify they fail**

Run: `cd /tmp/splintarr && poetry run pytest tests/unit/test_discord_started_notifications.py -v --no-cov`
Expected: FAIL — `AttributeError: 'DiscordNotificationService' object has no attribute 'send_search_started'`

**Step 3: Write implementation**

Add to `src/splintarr/services/discord.py`, after the `__init__` method and before `send_search_summary`:

```python
    async def send_search_started(
        self,
        search_name: str,
        instance_name: str,
        strategy: str,
        estimated_items: int,
    ) -> bool:
        """
        Send a search started notification (blue embed).

        Args:
            search_name: Name of the search queue
            instance_name: Name of the instance being searched
            strategy: Search strategy (e.g. 'missing', 'cutoff')
            estimated_items: Estimated number of items to evaluate

        Returns:
            bool: True if the webhook accepted the message
        """
        embed: dict = {
            "title": f"Search Started: {search_name}",
            "description": (
                f"**Instance:** {instance_name}\n"
                f"**Strategy:** {strategy}\n"
                f"**Items to evaluate:** {estimated_items}"
            ),
            "color": COLOR_BLUE,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "footer": {"text": "Splintarr"},
        }

        logger.info(
            "discord_notification_search_started",
            search_name=search_name,
            instance_name=instance_name,
            estimated_items=estimated_items,
        )

        return await self._send_embed(embed)
```

**Step 4: Run tests to verify they pass**

Run: `cd /tmp/splintarr && poetry run pytest tests/unit/test_discord_started_notifications.py -v --no-cov`
Expected: 2 passed

**Step 5: Commit**

```bash
cd /tmp/splintarr
git add src/splintarr/services/discord.py tests/unit/test_discord_started_notifications.py
git -c user.name="menottim" -c user.email="menottim@users.noreply.github.com" commit -m "feat: add send_search_started Discord notification method"
```

---

### Task 2: Add `send_library_sync_started` to Discord service

**Files:**
- Modify: `src/splintarr/services/discord.py` (insert after `send_search_started`)
- Modify: `tests/unit/test_discord_started_notifications.py` (append)

**Step 1: Write the failing tests**

Append to `tests/unit/test_discord_started_notifications.py`:

```python
class TestSendLibrarySyncStarted:
    """Test send_library_sync_started Discord embed."""

    @pytest.mark.asyncio
    async def test_sends_blue_embed(self):
        service = DiscordNotificationService("https://discord.com/api/webhooks/test")
        with patch.object(service, "_send_embed", new_callable=AsyncMock, return_value=True) as mock:
            result = await service.send_library_sync_started(instance_count=2)
            assert result is True
            embed = mock.call_args[0][0]
            assert embed["color"] == 0x3498DB  # COLOR_BLUE
            assert "Sync Started" in embed["title"]

    @pytest.mark.asyncio
    async def test_embed_includes_instance_count(self):
        service = DiscordNotificationService("https://discord.com/api/webhooks/test")
        with patch.object(service, "_send_embed", new_callable=AsyncMock, return_value=True) as mock:
            await service.send_library_sync_started(instance_count=3)
            embed = mock.call_args[0][0]
            assert "3" in embed["description"]
            assert "footer" in embed
            assert "timestamp" in embed
```

**Step 2: Run tests to verify new tests fail**

Run: `cd /tmp/splintarr && poetry run pytest tests/unit/test_discord_started_notifications.py::TestSendLibrarySyncStarted -v --no-cov`
Expected: FAIL — `AttributeError: 'DiscordNotificationService' object has no attribute 'send_library_sync_started'`

**Step 3: Write implementation**

Add to `src/splintarr/services/discord.py`, after `send_search_started`:

```python
    async def send_library_sync_started(
        self,
        instance_count: int,
    ) -> bool:
        """
        Send a library sync started notification (blue embed).

        Args:
            instance_count: Number of instances being synced

        Returns:
            bool: True if the webhook accepted the message
        """
        embed: dict = {
            "title": "Library Sync Started",
            "description": f"Syncing {instance_count} instance(s)...",
            "color": COLOR_BLUE,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "footer": {"text": "Splintarr"},
        }

        logger.info(
            "discord_notification_library_sync_started",
            instance_count=instance_count,
        )

        return await self._send_embed(embed)
```

**Step 4: Run all started notification tests**

Run: `cd /tmp/splintarr && poetry run pytest tests/unit/test_discord_started_notifications.py -v --no-cov`
Expected: 4 passed

**Step 5: Commit**

```bash
cd /tmp/splintarr
git add src/splintarr/services/discord.py tests/unit/test_discord_started_notifications.py
git -c user.name="menottim" -c user.email="menottim@users.noreply.github.com" commit -m "feat: add send_library_sync_started Discord notification method"
```

---

### Task 3: Dispatch search started notification in search_queue.py

**Files:**
- Modify: `src/splintarr/services/search_queue.py:172-183` (insert after `search_queue_execution_started` log, before `event_bus.emit`)

**Step 1: Write the dispatch helper**

Add `_notify_search_started` to `search_queue.py`, in the notification helpers section (after `_notify_queue_failed`, around line 1483):

```python
    async def _notify_search_started(
        self,
        db: Session,
        user_id: int,
        search_name: str,
        instance_name: str,
        strategy: str,
        estimated_items: int,
    ) -> None:
        """Send a search started Discord notification if configured and enabled."""
        try:
            config = (
                db.query(NotificationConfig)
                .filter(
                    NotificationConfig.user_id == user_id,
                    NotificationConfig.is_active.is_(True),
                )
                .first()
            )
            if not config or not config.is_event_enabled("search_triggered"):
                return

            webhook_url = decrypt_field(config.webhook_url)
            service = DiscordNotificationService(webhook_url)
            await service.send_search_started(
                search_name=search_name,
                instance_name=instance_name,
                strategy=strategy,
                estimated_items=estimated_items,
            )
        except Exception as e:
            logger.warning(
                "discord_notification_send_failed",
                event="search_started",
                user_id=user_id,
                error=str(e),
            )
```

**Step 2: Call the dispatch in execute_queue**

In `execute_queue()`, after the `search_queue_execution_started` log line (line 172) and before the `event_bus.emit("search.started", ...)` call (line 178), insert:

```python
            # Fire-and-forget: Discord notification for search started
            await self._notify_search_started(
                db=db,
                user_id=instance.user_id,
                search_name=queue.name,
                instance_name=instance.name,
                strategy=queue.strategy,
                estimated_items=queue.max_items_per_run or 50,
            )
```

**Step 3: Run existing tests to confirm no regressions**

Run: `cd /tmp/splintarr && poetry run pytest tests/ -v --no-cov -x`
Expected: All existing tests pass

**Step 4: Commit**

```bash
cd /tmp/splintarr
git add src/splintarr/services/search_queue.py
git -c user.name="menottim" -c user.email="menottim@users.noreply.github.com" commit -m "feat: dispatch search started Discord notification"
```

---

### Task 4: Dispatch library sync started notification in library.py

**Files:**
- Modify: `src/splintarr/api/library.py:73-93` (insert near top of `_run_sync_all_background`)

**Step 1: Write the dispatch helper**

Add `_notify_library_sync_started` to `api/library.py`, after `_notify_library_sync` (around line 190):

```python
async def _notify_library_sync_started(instance_count: int) -> None:
    """Send Discord notification for library sync start if configured."""
    try:
        from splintarr.core.security import decrypt_field
        from splintarr.models.notification import NotificationConfig
        from splintarr.services.discord import DiscordNotificationService

        db = get_session_factory()()
        try:
            config = (
                db.query(NotificationConfig)
                .filter(NotificationConfig.is_active.is_(True))
                .first()
            )
            if not config or not config.is_event_enabled("library_sync"):
                return

            webhook_url = decrypt_field(config.webhook_url)
            service = DiscordNotificationService(webhook_url)
            await service.send_library_sync_started(instance_count=instance_count)
        finally:
            db.close()
    except Exception as e:
        logger.warning(
            "discord_notification_send_failed",
            event="library_sync_started",
            error=str(e),
        )
```

**Step 2: Call the dispatch in _run_sync_all_background**

In `_run_sync_all_background()`, after the `library_sync_background_started` log line (line 90) and before `service = get_sync_service()` (line 92), we need to query the instance count and send the notification. Insert:

```python
        # Count active instances for notification
        from splintarr.models.instance import Instance

        _count_db = get_session_factory()()
        try:
            instance_count = _count_db.query(Instance).filter(Instance.is_active.is_(True)).count()
        finally:
            _count_db.close()

        # Fire-and-forget: Discord notification for sync start
        await _notify_library_sync_started(instance_count=instance_count)
```

**Step 3: Run existing tests to confirm no regressions**

Run: `cd /tmp/splintarr && poetry run pytest tests/ -v --no-cov -x`
Expected: All existing tests pass

**Step 4: Commit**

```bash
cd /tmp/splintarr
git add src/splintarr/api/library.py
git -c user.name="menottim" -c user.email="menottim@users.noreply.github.com" commit -m "feat: dispatch library sync started Discord notification"
```

---

### Task 5: Full test suite + lint check

**Files:** None (validation only)

**Step 1: Run full test suite with coverage**

Run: `cd /tmp/splintarr && poetry run pytest tests/ -v`
Expected: All tests pass, coverage >= 80%

**Step 2: Run linter**

Run: `cd /tmp/splintarr && poetry run ruff check src/`
Expected: No errors

**Step 3: Run type checker**

Run: `cd /tmp/splintarr && poetry run mypy src/`
Expected: No new errors

**Step 4: Run security linter**

Run: `cd /tmp/splintarr && poetry run bandit -r src/ -c pyproject.toml`
Expected: No new findings
