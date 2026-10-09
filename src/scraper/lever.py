"""
lever.py — Direct API scraper for Lever ATS portal.

Endpoint: GET https://api.lever.co/v0/postings/{company}?mode=json
Public, no authentication required.
"""

import logging

from src.scraper.base import (
    BaseScraper,
    clip_text,
    collect_companies,
    create_http_client,
    get_companies,
    get_with_retry,
    matches_filters,
)

logger = logging.getLogger(__name__)

_API_URL = "https://api.lever.co/v0/postings/{company}?mode=json"


class LeverScraper(BaseScraper):
    """Scraper for Lever job board API."""

    async def scrape_all(self) -> list[dict]:
        """Scrape all configured Lever companies."""
        companies = get_companies("lever")
        logger.info("[Lever] Starting scrape for %d companies", len(companies))

        async with create_http_client() as client:
            return await collect_companies(
                "Lever",
                companies,
                lambda slug: self._fetch_company(client, slug),
            )

    async def scrape_company(self, company_slug: str) -> list[dict]:
        """Scrape jobs from a single Lever company."""
        async with create_http_client() as client:
            return await self._fetch_company(client, company_slug)

    async def _fetch_company(self, client, company_slug: str) -> list[dict]:
        """Fetch and filter jobs from one Lever company.

        Lever API response format:
        [
          {
            "text": "Software Engineer",
            "hostedUrl": "https://jobs.lever.co/company/uuid",
            "categories": {
              "location": "Remote - Spain",
              "team": "Engineering",
              "commitment": "Full-time"
            },
            "description": "...",
            "lists": [...]
          },
          ...
        ]
        """
        url = _API_URL.format(company=company_slug)
        response = await get_with_retry(client, url)

        if response.status_code == 404:
            logger.debug("[Lever] Company not found: %s", company_slug)
            return []

        response.raise_for_status()
        postings = response.json()

        if not isinstance(postings, list):
            logger.warning("[Lever] Unexpected response format for %s", company_slug)
            return []

        jobs: list[dict] = []
        for posting in postings:
            title = posting.get("text", "")
            categories = posting.get("categories", {})
            location = categories.get("location", "")
            hosted_url = posting.get("hostedUrl", "")

            if not title or not hosted_url:
                continue

            if not matches_filters(title, location):
                continue

            jobs.append({
                "title": title,
                "company": company_slug.replace("-", " ").title(),
                "url": hosted_url,
                "location": location,
                "ats_type": "lever",
                "description": clip_text(
                    posting.get("descriptionPlain") or posting.get("description")
                ),
            })

        logger.info(
            "[Lever] %s — %d jobs matched filters (out of %d total)",
            company_slug,
            len(jobs),
            len(postings),
        )
        return jobs
