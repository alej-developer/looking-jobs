"""Process entrypoint. Refuses any bind address that is not loopback."""

from __future__ import annotations

import logging
import sys

import uvicorn

from config import API_HOST, API_PORT
from src.api.auth import expected_token

logger = logging.getLogger(__name__)

_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})
_MIN_TOKEN_LENGTH = 24


def assert_server_config() -> None:
    """Fail closed before opening a socket."""
    if API_HOST not in _LOOPBACK:
        print(
            "[API] Refusing to bind a non-loopback host. Set API_HOST=127.0.0.1.",
            file=sys.stderr,
        )
        sys.exit(1)
    token = expected_token()
    if len(token) < _MIN_TOKEN_LENGTH:
        print(
            "[API] API_TOKEN is missing or shorter than 24 characters. "
            "Set one in .env and retry. The token is not printed.",
            file=sys.stderr,
        )
        sys.exit(1)


def run() -> None:
    """Start uvicorn on the configured loopback port."""
    assert_server_config()
    logger.info("Starting local API on %s:%s", API_HOST, API_PORT)
    uvicorn.run(
        "src.api.app:create_app",
        factory=True,
        host=API_HOST,
        port=API_PORT,
        log_level="info",
        access_log=False,
        server_header=False,
        date_header=False,
    )
