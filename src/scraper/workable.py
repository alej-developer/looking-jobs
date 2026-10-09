"""
workable.py — Direct API scraper for Workable ATS portal.

Endpoint: GET https://apply.workable.com/api/v1/widget/accounts/{company}
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

_API_URL = "https://apply.workable.com/api/v1/widget/accounts/{company}"


class WorkableScraper(BaseScraper):
    """Scraper for Workable job board API."""

    async def scrape_all(self) -> list[dict]:
        """Scrape all configured Workable companies."""
        companies = get_companies("workable")
        logger.info("[Workable] Starting scrape for %d companies", len(companies))

        async with create_http_client() as client:
            return await collect_companies(
                "Workable",
                companies,
                lambda slug: self._fetch_company(client, slug),
            )

    async def scrape_company(self, company_slug: str) -> list[dict]:
        """Scrape jobs from a single Workable company."""
        async with create_http_client() as client:
            return await self._fetch_company(client, company_slug)

    async def _fetch_company(self, client, company_slug: str) -> list[dict]:
        """Fetch and filter jobs from one Workable company.

        Workable API response format:
        {
          "jobs": [
            {
              "title": "Backend Developer",
              "url": "https://apply.workable.com/company/j/UUID/",
              "city": "Madrid",
              "state": "Madrid",
              "country": "Spain",
              "department": "Engineering"
            },
            ...
          ]
        }
        """
        url = _API_URL.format(company=company_slug)
        response = await get_with_retry(client, url)

        if response.status_code == 404:
            logger.debug("[Workable] Company not found: %s", company_slug)
            return []

        response.raise_for_status()
        data = response.json()

        postings = data.get("jobs", [])
        if not isinstance(postings, list):
            logger.warning("[Workable] Unexpected response format for %s", company_slug)
            return []

        jobs: list[dict] = []
        for posting in postings:
            title = posting.get("title", "")
            city = posting.get("city", "")
            country = posting.get("country", "")
            location_parts = [p for p in (city, country) if p]
            location = ", ".join(location_parts)

            job_url = posting.get("url", "")

            if not title or not job_url:
                continue

            if not matches_filters(title, location):
                continue

            jobs.append({
                "title": title,
                "company": company_slug.replace("-", " ").title(),
                "url": job_url,
                "location": location,
                "ats_type": "workable",
                "description": clip_text(posting.get("description")),
            })

        logger.info(
            "[Workable] %s — %d jobs matched filters (out of %d total)",
            company_slug,
            len(jobs),
            len(postings),
        )
        return jobs
