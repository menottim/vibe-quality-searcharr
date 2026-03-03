# WebSocket Real-Time Activity Feed — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace all dashboard polling with a single WebSocket connection that pushes real-time events from services to the browser.

**Architecture:** Three new backend modules (EventBus, WebSocketManager, WS route) wire services to connected clients. Frontend gets a `Splintarr.ws` module in app.js that replaces all `setInterval` polling. Graceful fallback to polling after 3 failed reconnects.

**Tech Stack:** FastAPI WebSocket (built-in via Starlette), asyncio for event bus, vanilla JS WebSocket API.

**Design doc:** `docs/plans/2026-03-03-websocket-design.md`

---

### Task 1: EventBus Core Module

**Files:**
- Create: `src/splintarr/core/events.py`
- Test: `tests/unit/test_events.py`

**Step 1: Write the failing test**

Create `tests/unit/test_events.py`:

```python
"""Tests for the in-process event bus."""

import asyncio

import pytest

from splintarr.core.events import EventBus


@pytest.fixture
def bus():
    return EventBus()


class TestEventBus:
    async def test_emit_calls_registered_handler(self, bus):
        received = []
        bus.on("test.event", lambda data: received.append(data))
        await bus.emit("test.event", {"key": "value"})
        assert received == [{"key": "value"}]

    async def test_emit_calls_multiple_handlers(self, bus):
        results = []
        bus.on("test.event", lambda d: results.append("a"))
        bus.on("test.event", lambda d: results.append("b"))
        await bus.emit("test.event", {})
        assert sorted(results) == ["a", "b"]

    async def test_emit_unregistered_event_is_noop(self, bus):
        await bus.emit("no.handlers", {"key": "value"})  # Should not raise

    async def test_off_removes_handler(self, bus):
        received = []
        handler = lambda d: received.append(d)
        bus.on("test.event", handler)
        bus.off("test.event", handler)
        await bus.emit("test.event", {"key": "value"})
        assert received == []

    async def test_off_nonexistent_handler_is_noop(self, bus):
        bus.off("no.event", lambda d: None)  # Should not raise

    async def test_async_handler(self, bus):
        received = []

        async def async_handler(data):
            received.append(data)

        bus.on("test.event", async_handler)
        await bus.emit("test.event", {"async": True})
        assert received == [{"async": True}]

    async def test_handler_exception_does_not_break_others(self, bus):
        received = []

        def bad_handler(data):
            raise ValueError("boom")

        bus.on("test.event", bad_handler)
        bus.on("test.event", lambda d: received.append(d))
        await bus.emit("test.event", {"key": "value"})
        assert received == [{"key": "value"}]
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_events.py -v --no-cov`
Expected: ImportError — `splintarr.core.events` does not exist

**Step 3: Write minimal implementation**

Create `src/splintarr/core/events.py`:

```python
"""
In-process async event bus for real-time WebSocket broadcasting.

Services emit events (e.g., search started, item searched) and the
WebSocketManager listens to broadcast them to connected clients.
"""

import asyncio
import inspect
from typing import Any, Callable

import structlog

logger = structlog.get_logger()


class EventBus:
    """In-process async event bus."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable]] = {}

    def on(self, event_type: str, handler: Callable) -> None:
        """Register a handler for an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def off(self, event_type: str, handler: Callable) -> None:
        """Remove a handler for an event type."""
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    async def emit(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit an event to all registered handlers."""
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            try:
                result = handler(data)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.warning(
                    "event_handler_error",
                    event_type=event_type,
                    handler=handler.__name__ if hasattr(handler, "__name__") else str(handler),
                )


# Module-level singleton
event_bus = EventBus()
```

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_events.py -v --no-cov`
Expected: All 7 tests PASS

**Step 5: Commit**

```
feat(ws): add EventBus core module for real-time event dispatching
```

---

### Task 2: WebSocketManager Core Module

**Files:**
- Create: `src/splintarr/core/websocket.py`
- Test: `tests/unit/test_websocket_manager.py`

**Step 1: Write the failing test**

Create `tests/unit/test_websocket_manager.py`:

```python
"""Tests for the WebSocket connection manager."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from splintarr.core.websocket import WebSocketManager


@pytest.fixture
def manager():
    return WebSocketManager()


def make_mock_ws(accept=True):
    """Create a mock WebSocket."""
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    return ws


class TestWebSocketManager:
    async def test_connect_registers_websocket(self, manager):
        ws = make_mock_ws()
        await manager.connect(ws)
        assert len(manager.active_connections) == 1

    async def test_disconnect_removes_websocket(self, manager):
        ws = make_mock_ws()
        await manager.connect(ws)
        manager.disconnect(ws)
        assert len(manager.active_connections) == 0

    async def test_disconnect_nonexistent_is_noop(self, manager):
        ws = make_mock_ws()
        manager.disconnect(ws)  # Should not raise

    async def test_broadcast_sends_to_all(self, manager):
        ws1 = make_mock_ws()
        ws2 = make_mock_ws()
        await manager.connect(ws1)
        await manager.connect(ws2)
        await manager.broadcast({"type": "test", "data": {}})
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()

    async def test_broadcast_removes_dead_connections(self, manager):
        ws_good = make_mock_ws()
        ws_dead = make_mock_ws()
        ws_dead.send_json.side_effect = Exception("connection closed")
        await manager.connect(ws_good)
        await manager.connect(ws_dead)
        await manager.broadcast({"type": "test", "data": {}})
        assert len(manager.active_connections) == 1

    async def test_broadcast_to_empty_is_noop(self, manager):
        await manager.broadcast({"type": "test", "data": {}})  # Should not raise

    async def test_connection_count(self, manager):
        assert manager.connection_count == 0
        ws = make_mock_ws()
        await manager.connect(ws)
        assert manager.connection_count == 1
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_websocket_manager.py -v --no-cov`
Expected: ImportError — `splintarr.core.websocket` does not exist

**Step 3: Write minimal implementation**

Create `src/splintarr/core/websocket.py`:

```python
"""
WebSocket connection manager for real-time client broadcasting.

Maintains a registry of active WebSocket connections and broadcasts
events from the EventBus to all connected clients.
"""

from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import WebSocket

logger = structlog.get_logger()


class WebSocketManager:
    """Manages WebSocket connections and broadcasts events."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("websocket_connected", connections=len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the registry."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info("websocket_disconnected", connections=len(self.active_connections))

    @property
    def connection_count(self) -> int:
        """Number of active connections."""
        return len(self.active_connections)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a message to all connected clients. Remove dead connections."""
        if not self.active_connections:
            return

        message["timestamp"] = datetime.now(timezone.utc).isoformat()
        dead: list[WebSocket] = []

        for ws in self.active_connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self.disconnect(ws)

    async def send_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Broadcast a typed event to all clients."""
        await self.broadcast({"type": event_type, "data": data})


# Module-level singleton
ws_manager = WebSocketManager()
```

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_websocket_manager.py -v --no-cov`
Expected: All 7 tests PASS

**Step 5: Commit**

```
feat(ws): add WebSocketManager for connection registry and broadcasting
```

---

### Task 3: WebSocket Route and Startup Wiring

**Files:**
- Create: `src/splintarr/api/ws.py`
- Modify: `src/splintarr/main.py` (router registration + lifespan wiring)

**Step 1: Create the WebSocket route**

Create `src/splintarr/api/ws.py`:

```python
"""
WebSocket endpoint for real-time activity feed.

Provides a single WebSocket connection at /ws/live that replaces all
dashboard polling. Authenticates via access_token cookie on handshake.
"""

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from splintarr.core.auth import TokenError, get_current_user_id_from_token
from splintarr.core.websocket import ws_manager
from splintarr.database import get_db

logger = structlog.get_logger()

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    """
    Real-time activity feed WebSocket endpoint.

    Authenticates via access_token cookie from the handshake headers.
    On connect, sends current system state. Then keeps connection open
    for server-pushed events.
    """
    # Authenticate from cookie
    token = websocket.cookies.get("access_token")
    if not token:
        await websocket.close(code=4001, reason="Not authenticated")
        return

    try:
        user_id = get_current_user_id_from_token(token)
    except TokenError:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Accept and register connection
    await ws_manager.connect(websocket)
    logger.debug("websocket_client_connected", user_id=user_id)

    try:
        # Send initial state so client has current data immediately
        await _send_initial_state(websocket)

        # Keep connection alive — listen for client messages (pong, etc.)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        logger.debug("websocket_client_disconnected", user_id=user_id)
    except Exception:
        ws_manager.disconnect(websocket)


async def _send_initial_state(websocket: WebSocket) -> None:
    """Send current stats/status/indexer data on connect."""
    # Minimal initial state — services will emit full updates on their next cycle
    # This avoids DB queries in the WS handler (keep it lightweight)
    from splintarr.services.scheduler import get_scheduler_status

    await websocket.send_json({
        "type": "status.updated",
        "data": {
            "services": {
                "scheduler": get_scheduler_status(),
            },
        },
    })
```

**Step 2: Wire into main.py**

In `src/splintarr/main.py`:

Add import after the existing router imports:
```python
from splintarr.api import ws
```

Add router registration after `app.include_router(config.router)` (line 281):
```python
app.include_router(ws.router)
```

In the lifespan startup section (after `logger.info("library_sync_service_ready")` around line 108), add EventBus → WebSocketManager wiring:
```python
        # Wire event bus to WebSocket manager
        from splintarr.core.events import event_bus
        from splintarr.core.websocket import ws_manager

        async def ws_broadcast(event_type: str):
            async def handler(data):
                await ws_manager.send_event(event_type, data)
            return handler

        for evt in [
            "search.started", "search.item_result", "search.completed",
            "search.failed", "stats.updated", "activity.updated",
            "status.updated", "indexer_health.updated",
            "sync.progress", "sync.completed",
        ]:
            event_bus.on(evt, await ws_broadcast(evt))

        logger.info("websocket_event_bus_wired")
```

**Step 3: Run tests to verify nothing broken**

Run: `.venv/bin/python -m pytest tests/unit/ --no-cov -q`
Expected: Same pass/fail count as before (682 passed, 42 failed pre-existing)

**Step 4: Commit**

```
feat(ws): add WebSocket route /ws/live and wire event bus to manager
```

---

### Task 4: Emit Events from Search Queue Service

**Files:**
- Modify: `src/splintarr/services/search_queue.py`

**Step 1: Add event_bus import and emit calls**

At the top of `search_queue.py`, add import:
```python
from splintarr.core.events import event_bus
```

After the `search_queue_execution_started` log (line 170-175), add:
```python
        await event_bus.emit("search.started", {
            "queue_id": queue_id,
            "queue_name": queue.name,
            "strategy": queue.strategy,
            "max_items": queue.max_items_per_run,
        })
```

After the `search_queue_execution_completed` log (line 262-268), add:
```python
            await event_bus.emit("search.completed", {
                "queue_id": queue_id,
                "queue_name": queue.name,
                "status": result["status"],
                "items_searched": result["items_searched"],
                "items_found": result["items_found"],
            })
            await event_bus.emit("stats.updated", {})  # Trigger dashboard refresh
            await event_bus.emit("activity.updated", {})
```

After each per-item search (around line 786-800, after `cmd_result = await search_fn([item_id])`), add:
```python
            await event_bus.emit("search.item_result", {
                "queue_id": queue_id,
                "item_name": label,
                "result": "found",
                "score": score,
                "score_reason": reason,
            })
```

After search failure for an item (in the except block), add:
```python
            await event_bus.emit("search.item_result", {
                "queue_id": queue_id,
                "item_name": label,
                "result": "failed",
                "score": score,
                "score_reason": reason,
            })
```

In the overall execution failure handler, add:
```python
        await event_bus.emit("search.failed", {
            "queue_id": queue_id,
            "error": str(e),
        })
```

**Step 2: Run tests**

Run: `.venv/bin/python -m pytest tests/unit/ --no-cov -q`
Expected: Same pass/fail count — event emissions are fire-and-forget, no test impact

**Step 3: Commit**

```
feat(ws): emit search events from queue execution service
```

---

### Task 5: Emit Events from Library Sync and Health Check

**Files:**
- Modify: `src/splintarr/api/library.py`
- Modify: `src/splintarr/services/scheduler.py`

**Step 1: Add sync progress events**

In `src/splintarr/api/library.py`, import the event bus:
```python
from splintarr.core.events import event_bus
```

In `_update_sync_progress()` (line 112-130), add at the end of the function:
```python
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(event_bus.emit("sync.progress", dict(_sync_state)))
    except RuntimeError:
        pass  # No event loop — skip WS broadcast
```

After sync completion in `_run_sync_all_background()` (around line 100), add:
```python
        await event_bus.emit("sync.completed", {
            "instances_synced": result.get("instances_synced", 0),
            "total_items": result.get("total_items", 0),
            "errors": result.get("errors", []),
        })
        await event_bus.emit("stats.updated", {})  # Library stats changed
```

**Step 2: Add health check events**

In `src/splintarr/services/scheduler.py`, import the event bus:
```python
from splintarr.core.events import event_bus
```

In `_execute_health_check()` (line 454-468), after processing results:
```python
            await event_bus.emit("status.updated", {})  # Trigger system status refresh
```

**Step 3: Run tests**

Run: `.venv/bin/python -m pytest tests/unit/ --no-cov -q`
Expected: Same pass/fail count

**Step 4: Commit**

```
feat(ws): emit events from library sync and health check services
```

---

### Task 6: Frontend WebSocket Client in app.js

**Files:**
- Modify: `src/splintarr/static/js/app.js`

**Step 1: Add Splintarr.ws module**

Add before the `window.Splintarr` export (line 194), insert the WebSocket client module:

```javascript
// WebSocket real-time connection
var SplintarrWS = (function() {
    var socket = null;
    var handlers = {};
    var reconnectAttempts = 0;
    var MAX_RECONNECT = 3;
    var reconnectTimer = null;
    var fallbackActive = false;
    var _onConnected = null;
    var _onFallback = null;

    function connect() {
        if (socket && socket.readyState <= 1) return; // Already open or connecting
        var protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        socket = new WebSocket(protocol + '//' + location.host + '/ws/live');

        socket.onopen = function() {
            reconnectAttempts = 0;
            fallbackActive = false;
            if (_onConnected) _onConnected();
        };

        socket.onmessage = function(event) {
            var msg;
            try { msg = JSON.parse(event.data); } catch (e) { return; }
            if (msg.type === 'auth.expired') {
                fetch('/api/auth/refresh', { method: 'POST' }).then(function() {
                    connect();
                }).catch(function() {
                    fallbackActive = true;
                    if (_onFallback) _onFallback();
                });
                return;
            }
            var fns = handlers[msg.type] || [];
            for (var i = 0; i < fns.length; i++) {
                try { fns[i](msg.data, msg.timestamp); } catch (e) { /* handler error */ }
            }
        };

        socket.onclose = function() {
            socket = null;
            reconnectAttempts++;
            if (reconnectAttempts <= MAX_RECONNECT) {
                var delay = Math.min(1000 * Math.pow(2, reconnectAttempts - 1), 30000);
                reconnectTimer = setTimeout(connect, delay);
            } else {
                fallbackActive = true;
                if (_onFallback) _onFallback();
                // Keep trying in background every 60s
                reconnectTimer = setTimeout(function() {
                    reconnectAttempts = 0;
                    connect();
                }, 60000);
            }
        };

        socket.onerror = function() {
            // onclose will fire after onerror
        };
    }

    function on(type, fn) {
        if (!handlers[type]) handlers[type] = [];
        handlers[type].push(fn);
    }

    function close() {
        if (reconnectTimer) clearTimeout(reconnectTimer);
        if (socket) socket.close();
        socket = null;
    }

    return {
        connect: connect,
        on: on,
        close: close,
        get connected() { return socket && socket.readyState === 1; },
        get usingFallback() { return fallbackActive; },
        set onConnected(fn) { _onConnected = fn; },
        set onFallback(fn) { _onFallback = fn; },
    };
})();
```

Then add `ws: SplintarrWS` to the `window.Splintarr` export object.

**Step 2: Run lint**

Run: No lint for JS in this project — visual verification only.

**Step 3: Commit**

```
feat(ws): add WebSocket client module to app.js
```

---

### Task 7: Dashboard Frontend Migration

**Files:**
- Modify: `src/splintarr/templates/dashboard/index.html`

**Step 1: Replace polling with WebSocket handlers**

This is the largest frontend change. In the `{% block extra_scripts %}` section:

1. **Keep** all existing DOM-building functions (`buildStatusRow`, `buildIntegrationRow`, `buildServiceRow`, `buildSectionLabel`, `buildIndexerRow`, `updateActivityTable`, `refreshIndexerHealth`).

2. **Remove** all four `setInterval` blocks and the `refreshActivity()` call.

3. **Add** WebSocket handler registrations and a polling fallback:

```javascript
// --- WebSocket real-time updates ---
var pollingTimers = [];

function startPolling() {
    // Fallback polling (same as the original setInterval blocks)
    pollingTimers.push(setInterval(pollStats, 30000));
    pollingTimers.push(setInterval(pollSystemStatus, 30000));
    pollingTimers.push(setInterval(pollActivity, 15000));
    pollingTimers.push(setInterval(pollIndexerHealth, 60000));
    pollActivity();
    pollIndexerHealth();
}

function stopPolling() {
    pollingTimers.forEach(function(t) { clearInterval(t); });
    pollingTimers = [];
}

// Extract existing polling logic into named functions
// (pollStats, pollSystemStatus, pollActivity, pollIndexerHealth)
// These are the existing setInterval callbacks, just named.

// Register WS handlers
Splintarr.ws.on('stats.updated', function(data) {
    // Reuse existing stats update logic
    if (data.search_queues) { /* update stat cards */ }
});

Splintarr.ws.on('status.updated', function(data) {
    statusLastChecked = Date.now();
    // Reuse existing system status update logic
});

Splintarr.ws.on('activity.updated', function(data) {
    if (data.activity) updateActivityTable(data.activity);
});

Splintarr.ws.on('indexer_health.updated', function(data) {
    refreshIndexerHealthFromData(data);
});

// Fallback
Splintarr.ws.onConnected = stopPolling;
Splintarr.ws.onFallback = startPolling;

// Start WebSocket connection
Splintarr.ws.connect();

// If WS doesn't connect within 2 seconds, start polling as safety net
setTimeout(function() {
    if (!Splintarr.ws.connected) startPolling();
}, 2000);
```

The exact implementation details for each handler mirror the existing `setInterval` callback bodies — the DOM update functions are reused, only the data delivery mechanism changes.

**Step 2: Test manually**

Build Docker, verify dashboard loads with WebSocket connected, verify fallback works by stopping the server and restarting.

**Step 3: Commit**

```
feat(ws): migrate dashboard polling to WebSocket with fallback
```

---

### Task 8: Library and Queue Detail Page Migration

**Files:**
- Modify: `src/splintarr/templates/library.html`
- Modify: `src/splintarr/templates/search_queue_detail.html`

**Step 1: Library sync progress via WebSocket**

In `library.html`, the existing 2-second sync polling (lines 154-176) should be supplemented with a WS handler:

```javascript
Splintarr.ws.on('sync.progress', function(data) {
    updateSyncProgress(data);
});
Splintarr.ws.on('sync.completed', function(data) {
    // Refresh the page to show updated library
    window.location.reload();
});
```

Keep the existing 2-second polling as fallback (only runs during active sync).

**Step 2: Queue detail execution progress via WebSocket**

In `search_queue_detail.html`, the existing 3-second polling (lines 349-371) should be supplemented:

```javascript
Splintarr.ws.on('search.started', function(data) {
    if (data.queue_id == queueId) showExecutionProgress(data);
});
Splintarr.ws.on('search.item_result', function(data) {
    if (data.queue_id == queueId) appendItemResult(data);
});
Splintarr.ws.on('search.completed', function(data) {
    if (data.queue_id == queueId) showExecutionComplete(data);
});
```

**Step 3: Test manually**

Trigger a library sync and queue execution, verify real-time updates appear.

**Step 4: Commit**

```
feat(ws): migrate library sync and queue detail polling to WebSocket
```

---

### Task 9: Docker Build, Integration Test, and Cleanup

**Files:**
- Modify: `src/splintarr/templates/base.html` (add `beforeunload` cleanup)

**Step 1: Add cleanup in base.html**

In the global script block of `base.html` (around line 117), add:
```javascript
window.addEventListener('beforeunload', function() {
    if (Splintarr.ws) Splintarr.ws.close();
});
```

**Step 2: Run full test suite**

Run: `.venv/bin/python -m pytest tests/unit/ --no-cov -q`
Expected: 684+ passed (2 new test files), 42 failed (pre-existing)

**Step 3: Lint check**

Run: `.venv/bin/ruff check src/splintarr/core/events.py src/splintarr/core/websocket.py src/splintarr/api/ws.py`
Expected: All checks passed

**Step 4: Docker build and manual verification**

```bash
docker-compose build && docker-compose up -d
# Wait for health
curl http://localhost:7337/health
# Open browser, verify WebSocket connects (check browser DevTools Network tab for /ws/live)
# Verify dashboard updates without polling
# Trigger a search queue, verify real-time item results appear
docker-compose down
```

**Step 5: Final commit**

```
feat(ws): add cleanup handler and verify integration
```

---

## Implementation Order Summary

| Task | Description | Effort | Dependencies |
|------|-------------|--------|-------------|
| 1 | EventBus core module + tests | Low | None |
| 2 | WebSocketManager + tests | Low | None |
| 3 | WS route + main.py wiring | Low | Tasks 1-2 |
| 4 | Search queue event emissions | Low | Task 1 |
| 5 | Library sync + health check events | Low | Task 1 |
| 6 | Frontend WS client (app.js) | Medium | None |
| 7 | Dashboard migration | Medium | Tasks 3, 6 |
| 8 | Library + queue detail migration | Low | Tasks 5, 6 |
| 9 | Integration test + cleanup | Low | All |

Tasks 1-2 can be done in parallel. Tasks 4-5 can be done in parallel. Task 6 can be done in parallel with 3-5.
