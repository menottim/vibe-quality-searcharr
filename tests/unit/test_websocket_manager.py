"""
Unit tests for WebSocketManager.

Tests connection registration, disconnection, broadcasting, and dead connection cleanup.
"""

from unittest.mock import AsyncMock

from splintarr.core.websocket import WebSocketManager


def _make_mock_ws() -> AsyncMock:
    """Create a mock WebSocket with async accept, send_json, and close methods."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    return ws


class TestWebSocketManager:
    """Tests for WebSocketManager connection registry and broadcasting."""

    def setup_method(self) -> None:
        """Create a fresh manager for each test."""
        self.manager = WebSocketManager()

    async def test_connect_registers_websocket(self) -> None:
        """Connecting a WebSocket accepts it and adds it to active connections."""
        ws = _make_mock_ws()

        await self.manager.connect(ws)

        ws.accept.assert_awaited_once()
        assert ws in self.manager.active_connections
        assert self.manager.connection_count == 1

    async def test_disconnect_removes_websocket(self) -> None:
        """Disconnecting a registered WebSocket removes it from active connections."""
        ws = _make_mock_ws()
        await self.manager.connect(ws)

        self.manager.disconnect(ws)

        assert ws not in self.manager.active_connections
        assert self.manager.connection_count == 0

    async def test_disconnect_nonexistent_is_noop(self) -> None:
        """Disconnecting a WebSocket that was never connected does nothing."""
        ws = _make_mock_ws()

        # Should not raise
        self.manager.disconnect(ws)

        assert self.manager.connection_count == 0

    async def test_broadcast_sends_to_all(self) -> None:
        """Broadcasting sends the message (with timestamp) to every connection."""
        ws1 = _make_mock_ws()
        ws2 = _make_mock_ws()
        await self.manager.connect(ws1)
        await self.manager.connect(ws2)

        message = {"type": "test", "data": {"value": 42}}
        await self.manager.broadcast(message)

        # Both should receive the message with a timestamp added
        assert ws1.send_json.await_count == 1
        assert ws2.send_json.await_count == 1
        sent1 = ws1.send_json.call_args[0][0]
        sent2 = ws2.send_json.call_args[0][0]
        assert sent1["type"] == "test"
        assert sent1["data"] == {"value": 42}
        assert "timestamp" in sent1
        assert sent2["type"] == "test"
        assert "timestamp" in sent2

    async def test_broadcast_removes_dead_connections(self) -> None:
        """Broadcasting removes connections that raise exceptions on send."""
        ws_alive = _make_mock_ws()
        ws_dead = _make_mock_ws()
        ws_dead.send_json = AsyncMock(side_effect=Exception("connection closed"))
        await self.manager.connect(ws_alive)
        await self.manager.connect(ws_dead)

        message = {"type": "ping"}
        await self.manager.broadcast(message)

        # Dead connection should be removed
        assert ws_dead not in self.manager.active_connections
        # Alive connection should remain
        assert ws_alive in self.manager.active_connections
        assert self.manager.connection_count == 1

    async def test_broadcast_to_empty_is_noop(self) -> None:
        """Broadcasting with no connections does nothing and doesn't raise."""
        message = {"type": "test"}
        # Should not raise
        await self.manager.broadcast(message)

    async def test_connection_count(self) -> None:
        """connection_count property reflects the number of active connections."""
        assert self.manager.connection_count == 0

        ws1 = _make_mock_ws()
        ws2 = _make_mock_ws()
        ws3 = _make_mock_ws()
        await self.manager.connect(ws1)
        assert self.manager.connection_count == 1

        await self.manager.connect(ws2)
        assert self.manager.connection_count == 2

        await self.manager.connect(ws3)
        assert self.manager.connection_count == 3

        self.manager.disconnect(ws2)
        assert self.manager.connection_count == 2

    async def test_send_event_wraps_and_broadcasts(self) -> None:
        """send_event wraps type and data into a message and broadcasts it."""
        ws = _make_mock_ws()
        await self.manager.connect(ws)

        await self.manager.send_event("search_started", {"queue_id": 5})

        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "search_started"
        assert sent["data"] == {"queue_id": 5}
        assert "timestamp" in sent
