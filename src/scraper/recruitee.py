"""
recruitee.py — Direct API scraper for Recruitee ATS portal.

Endpoint: GET https://{company}.recruitee.com/api/offers/
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

_API_URL = "https://{company}.recruitee.com/api/offers/"


class RecruiteeScraper(BaseScraper):
    """Scraper for Recruitee job board API."""

    async def scrape_all(self) -> list[dict]:
        """Scrape all configured Recruitee companies."""
        companies = get_companies("recruitee")
        all_jobs: list[dict] = []

        logger.info("[Recruitee] Starting scrape for %d companies", len(companies))

        async with create_http_client() as client:
            for slug in companies:
                try:
                    jobs = await self._fetch_company(client, slug)
                    all_jobs.extend(jobs)
                except Exception:
                    logger.exception("[Recruitee] Failed to scrape company: %s", slug)

        logger.info("[Recruitee] Total filtered jobs found: %d", len(all_jobs))
        return all_jobs

    async def scrape_company(self, company_slug: str) -> list[dict]:
        """Scrape jobs from a single Recruitee company."""
        async with create_http_client() as client:
            return await self._fetch_company(client, company_slug)

    async def _fetch_company(self, client, company_slug: str) -> list[dict]:
        """Fetch and filter jobs from one Recruitee company.

        Recruitee API response format:
        {
          "offers": [
            {
              "title": "Python Developer",
              "careers_url": "https://company.recruitee.com/o/python-developer",
              "location": "Remote - Spain",
              "department": "Engineering"
            },
            ...
          ]
        }
        """
        url = _API_URL.format(company=company_slug)
        response = await client.get(url)

        if response.status_code == 404:
            logger.debug("[Recruitee] Company not found: %s", company_slug)
            return []

        response.raise_for_status()
        data = response.json()

        postings = data.get("offers", [])
        if not isinstance(postings, list):
            logger.warning("[Recruitee] Unexpected response format for %s", company_slug)
            return []

        jobs: list[dict] = []
        for posting in postings:
            title = posting.get("title", "")
            location = posting.get("location", "")
            careers_url = posting.get("careers_url", "")

            if not title or not careers_url:
                continue

            if not matches_filters(title, location):
                continue

            jobs.append({
                "title": title,
                "company": company_slug.replace("-", " ").title(),
                "url": careers_url,
                "location": location,
                "ats_type": "recruitee",
            })

        logger.info(
            "[Recruitee] %s — %d jobs matched filters (out of %d total)",
            company_slug,
            len(jobs),
            len(postings),
        )
        return jobs
