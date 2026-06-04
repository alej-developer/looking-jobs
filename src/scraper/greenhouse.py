"""
greenhouse.py — Direct API scraper for Greenhouse ATS portal.

Endpoint: GET https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true
Public, no authentication required.
"""

import logging

from src.scraper.base import (
    BaseScraper,
    create_http_client,
    get_companies,
    matches_filters,
)

logger = logging.getLogger(__name__)

_API_URL = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true"


class GreenhouseScraper(BaseScraper):
    """Scraper for Greenhouse job board API."""

    async def scrape_all(self) -> list[dict]:
        """Scrape all configured Greenhouse companies."""
        companies = get_companies("greenhouse")
        all_jobs: list[dict] = []

        logger.info("[Greenhouse] Starting scrape for %d companies", len(companies))

        async with create_http_client() as client:
            for slug in companies:
                try:
                    jobs = await self._fetch_company(client, slug)
                    all_jobs.extend(jobs)
                except Exception:
                    logger.exception("[Greenhouse] Failed to scrape company: %s", slug)

        logger.info("[Greenhouse] Total filtered jobs found: %d", len(all_jobs))
        return all_jobs

    async def scrape_company(self, company_slug: str) -> list[dict]:
        """Scrape jobs from a single Greenhouse company."""
        async with create_http_client() as client:
            return await self._fetch_company(client, company_slug)

    async def _fetch_company(self, client, company_slug: str) -> list[dict]:
        """Fetch and filter jobs from one Greenhouse company.

        Greenhouse API response format:
        {
          "jobs": [
            {
              "title": "Software Engineer",
              "absolute_url": "https://boards.greenhouse.io/company/jobs/123",
              "location": {"name": "Remote - Spain"},
              "departments": [{"name": "Engineering"}],
              "content": "..."
            },
            ...
          ]
        }
        """
        url = _API_URL.format(company=company_slug)
        response = await client.get(url)

        if response.status_code == 404:
            logger.debug("[Greenhouse] Company not found: %s", company_slug)
            return []

        response.raise_for_status()
        data = response.json()

        postings = data.get("jobs", [])
        if not isinstance(postings, list):
            logger.warning("[Greenhouse] Unexpected response format for %s", company_slug)
            return []

        jobs: list[dict] = []
        for posting in postings:
            title = posting.get("title", "")
            location_obj = posting.get("location", {})
            location = location_obj.get("name", "") if isinstance(location_obj, dict) else ""
            absolute_url = posting.get("absolute_url", "")

            if not title or not absolute_url:
                continue

            if not matches_filters(title, location):
                continue

            jobs.append({
                "title": title,
                "company": company_slug.replace("-", " ").title(),
                "url": absolute_url,
                "location": location,
                "ats_type": "greenhouse",
            })

        logger.info(
            "[Greenhouse] %s — %d jobs matched filters (out of %d total)",
            company_slug,
            len(jobs),
            len(postings),
        )
        return jobs
