"""
WebSocket endpoint for real-time activity feed.

Provides a single WebSocket connection at /ws/live that replaces all
dashboard polling. Authenticates via access_token cookie on handshake.
"""

import time

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from splintarr.config import settings
from splintarr.core.auth import TokenError, get_current_user_id_from_token
from splintarr.core.websocket import ws_manager
from splintarr.database import get_session_factory
from splintarr.models.user import User

logger = structlog.get_logger()

router = APIRouter(tags=["websocket"])

# Per-IP WebSocket connection rate limiting (#134)
_RATE_LIMIT_MAX = 10  # max connections per window
_RATE_LIMIT_WINDOW = 60  # window in seconds
_conn_attempts: dict[str, list[float]] = {}


def _is_rate_limited(ip: str) -> bool:
    """Check if an IP has exceeded the connection rate limit.

    Cleans up expired entries on each call to prevent unbounded growth.
    Returns True if the IP should be rejected.
    """
    now = time.monotonic()
    cutoff = now - _RATE_LIMIT_WINDOW

    # Clean up stale IPs to bound memory usage
    stale_ips = [k for k, v in _conn_attempts.items() if v[-1] < cutoff]
    for k in stale_ips:
        del _conn_attempts[k]

    # Trim timestamps for the current IP
    timestamps = _conn_attempts.get(ip, [])
    timestamps = [t for t in timestamps if t > cutoff]

    if len(timestamps) >= _RATE_LIMIT_MAX:
        _conn_attempts[ip] = timestamps
        return True

    timestamps.append(now)
    _conn_attempts[ip] = timestamps
    return False


@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    """Real-time activity feed WebSocket endpoint."""
    # Per-IP rate limiting — reject before doing any auth work
    client_ip = websocket.client.host if websocket.client else "unknown"
    if _is_rate_limited(client_ip):
        logger.warning("websocket_rate_limited", ip=client_ip)
        await websocket.close(code=4029, reason="Too many requests")
        return

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

    # Verify the user still exists and is active (token may outlive account)
    try:
        session_factory = get_session_factory()
        with session_factory() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.is_active:
                await websocket.close(code=4001, reason="Account inactive")
                return
    except Exception as e:
        logger.warning("websocket_user_check_failed", error=str(e), user_id=user_id)
        await websocket.close(code=4001, reason="Authentication error")
        return

    # Validate Origin header to prevent Cross-Site WebSocket Hijacking (CSWSH)
    origin = websocket.headers.get("origin", "")
    if origin:
        allowed_origins = list(settings.cors_origins) if settings.cors_origins else []
        # Also allow requests from the app's own host
        host = websocket.headers.get("host", "")
        if host:
            local_origins = [f"http://{host}", f"https://{host}"]
            allowed_origins.extend(local_origins)
        if origin not in allowed_origins:
            logger.warning(
                "websocket_origin_rejected",
                origin=origin,
                user_id=user_id,
            )
            await websocket.close(code=4003, reason="Origin not allowed")
            return

    await ws_manager.connect(websocket)
    logger.debug("websocket_client_connected", user_id=user_id)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        logger.debug("websocket_client_disconnected", user_id=user_id)
    except Exception as e:
        ws_manager.disconnect(websocket)
        logger.warning("websocket_unexpected_error", error=str(e), user_id=user_id)
