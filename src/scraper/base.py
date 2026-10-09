"""
base.py — Abstract base class and shared utilities for ATS portal scrapers.

Provides:
- BaseScraper ABC that every concrete scraper must implement.
- Filter logic to match job titles against keywords and exclude seniority levels.
- Company list loader from companies.json.
- Shared httpx client factory with retry logic.
"""

import asyncio
import json
import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_COMPANIES_FILE = Path(__file__).resolve().parent.parent.parent / "companies.json"
_config_cache: dict | None = None


def _load_config() -> dict:
    """Load and cache the companies.json configuration file.

    Returns:
        The parsed JSON config as a dict.
    """
    global _config_cache
    if _config_cache is None:
        try:
            with open(_COMPANIES_FILE, "r", encoding="utf-8") as f:
                _config_cache = json.load(f)
            logger.debug("Loaded companies config from %s", _COMPANIES_FILE)
        except FileNotFoundError:
            logger.error("companies.json not found at %s", _COMPANIES_FILE)
            _config_cache = {}
        except json.JSONDecodeError:
            logger.exception("Invalid JSON in companies.json")
            _config_cache = {}
    return _config_cache


def get_companies(platform: str) -> list[str]:
    """Get the list of company slugs for a given ATS platform.

    Args:
        platform: Platform key (e.g. 'lever', 'greenhouse', 'ashby').

    Returns:
        List of company slug strings.
    """
    config = _load_config()
    return config.get(platform, [])


def get_keywords_include() -> list[str]:
    """Get the list of keywords to match in job titles."""
    config = _load_config()
    return config.get("keywords_include", [])


def get_keywords_exclude() -> list[str]:
    """Get the list of seniority keywords to exclude from results."""
    config = _load_config()
    return config.get("keywords_exclude_seniority", [])


def get_locations() -> list[str]:
    """Get the list of target locations."""
    config = _load_config()
    return config.get("locations", [])


def _term_in(haystack: str, term: str) -> bool:
    """Match a configured keyword on word boundaries.

    Terms that end in punctuation only require a leading boundary so values
    like ``sr.`` still match.
    """
    cleaned = term.strip().lower()
    if not cleaned:
        return False
    pattern = rf"\b{re.escape(cleaned)}"
    if cleaned[-1].isalnum():
        pattern += r"\b"
    return re.search(pattern, haystack, re.IGNORECASE) is not None


def clip_text(value: object, limit: int = 8000) -> str:
    """Reduce ATS HTML to a bounded plain-text snippet."""
    if not isinstance(value, str):
        return ""
    text = re.sub(r"<[^>]*>", " ", value)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def matches_filters(
    title: str,
    location: str = "",
) -> bool:
    """Check if a job posting matches the keyword and location filters.

    Strategy:
    1. The title must contain at least one keyword from keywords_include.
    2. The title must NOT contain any keyword from keywords_exclude_seniority.
    3. The location (if available) must match at least one target location,
       OR the location filter is skipped if no location data is provided.

    Args:
        title: The job posting title.
        location: The job location string (can be empty).

    Returns:
        True if the job matches all filters, False otherwise.
    """
    title_lower = title.lower()
    location_lower = location.lower() if location else ""

    # 1. Must match at least one include keyword
    keywords = get_keywords_include()
    if not any(_term_in(title_lower, kw) for kw in keywords):
        return False

    # 2. Must NOT match any seniority exclusion keyword
    exclusions = get_keywords_exclude()
    if any(_term_in(title_lower, ex) for ex in exclusions):
        return False

    # 3. Location filter (skip if no location data available)
    if location_lower:
        locations = get_locations()
        if not any(_term_in(location_lower, loc) for loc in locations):
            return False

    return True


async def get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    attempts: int = 3,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> httpx.Response:
    """GET a public board URL, backing off on rate limits and transport errors."""
    pause = sleep or asyncio.sleep
    delay = 0.5
    last_error: Exception | None = None
    response: httpx.Response | None = None
    for attempt in range(attempts):
        try:
            response = await client.get(url)
        except httpx.TransportError as exc:
            last_error = exc
            response = None
        if response is not None and response.status_code not in {429, 500, 502, 503, 504}:
            return response
        if attempt < attempts - 1:
            await pause(delay)
            delay = min(delay * 2, 8)
    if response is not None:
        return response
    if last_error is not None:
        raise last_error
    raise httpx.TransportError("request failed without a response")


async def collect_companies(
    label: str,
    companies: list[str],
    fetch: Callable[[str], Awaitable[list[dict]]],
    *,
    concurrency: int = 4,
) -> list[dict]:
    """Fetch several companies at once, isolating a failure to one slug."""
    semaphore = asyncio.Semaphore(concurrency)

    async def one(slug: str) -> list[dict]:
        async with semaphore:
            try:
                return await fetch(slug)
            except Exception:
                logger.exception("[%s] Failed to scrape company: %s", label, slug)
                return []

    groups = await asyncio.gather(*(one(slug) for slug in companies))
    jobs = [job for group in groups for job in group]
    logger.info("[%s] Total filtered jobs found: %d", label, len(jobs))
    return jobs


def create_http_client() -> httpx.AsyncClient:
    """Create a shared httpx async client with sensible defaults.

    Returns:
        An ``httpx.AsyncClient`` with timeout, headers, and redirect following.
    """
    return httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=10.0),
        follow_redirects=True,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        },
    )


class BaseScraper(ABC):
    """Interface that every ATS scraper must implement."""

    @abstractmethod
    async def scrape_all(self) -> list[dict]:
        """Scrape all configured companies on this platform.

        Returns:
            A list of dicts with keys: 'title', 'company', 'url',
            'location', 'ats_type'.
        """

    @abstractmethod
    async def scrape_company(self, company_slug: str) -> list[dict]:
        """Scrape jobs from a single company on this platform.

        Args:
            company_slug: The company identifier used in the API URL.

        Returns:
            A list of filtered job dicts.
        """
