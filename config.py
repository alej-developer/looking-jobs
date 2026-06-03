"""
config.py — Centralized, secure configuration loader.

Reads all settings from environment variables via a .env file.
Uses python-dotenv to load values and os.getenv for safe access.
No secrets are ever hardcoded.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# ─── Load .env from the project root ─────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent
_dotenv_path = _PROJECT_ROOT / ".env"

if not _dotenv_path.exists():
    print(
        "[CONFIG ERROR] .env file not found at: {}\n"
        "Copy .env.example to .env and fill in your values.".format(_dotenv_path),
        file=sys.stderr,
    )
    sys.exit(1)

load_dotenv(dotenv_path=_dotenv_path)


# ─── Helper ──────────────────────────────────────────────────────────────────
def _get_env(key: str, *, default: str | None = None, required: bool = False) -> str:
    """Return an environment variable's value, with optional enforcement.

    Args:
        key: Name of the environment variable.
        default: Fallback value if the variable is unset. Ignored when
                 ``required`` is True.
        required: If True, abort the program when the variable is missing.

    Returns:
        The variable's string value.
    """
    value = os.getenv(key, default)
    if required and (value is None or value.strip() == ""):
        print(
            "[CONFIG ERROR] Required environment variable '{}' is not set.\n"
            "Check your .env file.".format(key),
            file=sys.stderr,
        )
        sys.exit(1)
    return value  # type: ignore[return-value]


# ─── General ─────────────────────────────────────────────────────────────────
APP_ENV: str = _get_env("APP_ENV", default="development")
LOG_LEVEL: str = _get_env("LOG_LEVEL", default="INFO")

# ─── Database ────────────────────────────────────────────────────────────────
DATABASE_URL: str = _get_env("DATABASE_URL", default="sqlite:///data/jobs.db")

# ─── Browser Automation ─────────────────────────────────────────────────────
HEADLESS_MODE: bool = _get_env("HEADLESS_MODE", default="true").lower() == "true"
BROWSER_SLOWMO_MS: int = int(_get_env("BROWSER_SLOWMO_MS", default="0"))
USER_AGENT: str = _get_env("USER_AGENT", default="")

# ─── Proxy ───────────────────────────────────────────────────────────────────
PROXY_SERVER: str = _get_env("PROXY_SERVER", default="")
PROXY_USERNAME: str = _get_env("PROXY_USERNAME", default="")
PROXY_PASSWORD: str = _get_env("PROXY_PASSWORD", default="")

# ─── Candidate Profile ──────────────────────────────────────────────────────
CANDIDATE_FULL_NAME: str = _get_env("CANDIDATE_FULL_NAME", required=True)
CANDIDATE_EMAIL: str = _get_env("CANDIDATE_EMAIL", required=True)
CANDIDATE_PHONE: str = _get_env("CANDIDATE_PHONE", default="")
RESUME_FILE_PATH: str = _get_env("RESUME_FILE_PATH", default="")
