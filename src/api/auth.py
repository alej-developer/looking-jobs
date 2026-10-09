"""Session and bearer authentication for the loopback API.

The long-lived API token is never written to a cookie. A successful login
stores a random session id in memory and in an HttpOnly cookie.
"""

from __future__ import annotations

import os
import secrets
import time
from collections import deque

from fastapi import HTTPException, Request

_SESSION_COOKIE = "lj_session"
_SESSION_TTL_SECONDS = 8 * 60 * 60
_MAX_LOGIN_FAILURES = 8
_LOGIN_WINDOW_SECONDS = 60

_sessions: dict[str, float] = {}
_login_failures: deque[float] = deque()


def expected_token() -> str:
    """Return the current API token from the environment, not a cached copy."""
    return os.environ.get("API_TOKEN", "")


def token_matches(presented: str) -> bool:
    """Compare tokens without raising when the lengths differ."""
    expected = expected_token()
    if not presented or not expected:
        return False
    presented_bytes = presented.encode("utf-8")
    expected_bytes = expected.encode("utf-8")
    if len(presented_bytes) != len(expected_bytes):
        return False
    return secrets.compare_digest(presented_bytes, expected_bytes)


def _prune_sessions(now: float) -> None:
    expired = [key for key, expiry in _sessions.items() if expiry <= now]
    for key in expired:
        _sessions.pop(key, None)


def login_allowed(now: float | None = None) -> bool:
    """Sliding window for failed login attempts in this process."""
    current = time.time() if now is None else now
    while _login_failures and current - _login_failures[0] > _LOGIN_WINDOW_SECONDS:
        _login_failures.popleft()
    return len(_login_failures) < _MAX_LOGIN_FAILURES


def record_login_failure(now: float | None = None) -> None:
    _login_failures.append(time.time() if now is None else now)


def start_session() -> str:
    """Create a random session id. The API token itself is not the cookie value."""
    now = time.time()
    _prune_sessions(now)
    session_id = secrets.token_urlsafe(32)
    _sessions[session_id] = now + _SESSION_TTL_SECONDS
    return session_id


def end_session(session_id: str | None) -> None:
    if session_id:
        _sessions.pop(session_id, None)


def session_is_valid(session_id: str | None) -> bool:
    if not session_id:
        return False
    now = time.time()
    _prune_sessions(now)
    expiry = _sessions.get(session_id)
    return expiry is not None and expiry > now


def bearer_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer":
        return ""
    return value.strip()


def require_auth(request: Request) -> None:
    """Accept a live session cookie or a bearer token. Query tokens are ignored."""
    if session_is_valid(request.cookies.get(_SESSION_COOKIE)):
        return
    if token_matches(bearer_token(request)):
        return
    raise HTTPException(status_code=401, detail="Authentication required")


def cookie_name() -> str:
    return _SESSION_COOKIE
