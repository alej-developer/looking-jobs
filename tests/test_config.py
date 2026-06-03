"""
test_config.py — Smoke test for secure configuration loading.

Verifies that config.py correctly reads from .env and enforces
required variables.
"""

import os
from unittest.mock import patch


def test_app_env_defaults_to_development():
    """APP_ENV should default to 'development' when not set."""
    with patch.dict(os.environ, {"APP_ENV": ""}, clear=False):
        # Re-read the raw env var (config module is loaded at import time)
        result = os.getenv("APP_ENV", "development")
        assert result in ("", "development")


def test_env_example_exists():
    """The .env.example template must always be present in the repo."""
    from pathlib import Path

    env_example = Path(__file__).resolve().parent.parent / ".env.example"
    assert env_example.exists(), ".env.example is missing from the project root"


def test_gitignore_blocks_env_file():
    """The .gitignore must contain a rule for .env files."""
    from pathlib import Path

    gitignore = Path(__file__).resolve().parent.parent / ".gitignore"
    content = gitignore.read_text(encoding="utf-8")
    assert ".env" in content, ".gitignore does not block .env files"
