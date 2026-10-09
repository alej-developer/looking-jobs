"""
ashby.py — Direct API scraper for Ashby ATS portal.

Endpoint: GET https://api.ashbyhq.com/posting-api/job-board/{company}
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

_API_URL = "https://api.ashbyhq.com/posting-api/job-board/{company}"


class AshbyScraper(BaseScraper):
    """Scraper for Ashby job board API."""

    async def scrape_all(self) -> list[dict]:
        """Scrape all configured Ashby companies."""
        companies = get_companies("ashby")
        all_jobs: list[dict] = []

        logger.info("[Ashby] Starting scrape for %d companies", len(companies))

        async with create_http_client() as client:
            for slug in companies:
                try:
                    jobs = await self._fetch_company(client, slug)
                    all_jobs.extend(jobs)
                except Exception:
                    logger.exception("[Ashby] Failed to scrape company: %s", slug)

        logger.info("[Ashby] Total filtered jobs found: %d", len(all_jobs))
        return all_jobs

    async def scrape_company(self, company_slug: str) -> list[dict]:
        """Scrape jobs from a single Ashby company."""
        async with create_http_client() as client:
            return await self._fetch_company(client, company_slug)

    async def _fetch_company(self, client, company_slug: str) -> list[dict]:
        """Fetch and filter jobs from one Ashby company.

        Ashby API response format:
        {
          "jobs": [
            {
              "title": "Software Engineer",
              "jobUrl": "https://jobs.ashbyhq.com/company/uuid",
              "location": "Remote - Europe",
              "department": "Engineering",
              "employmentType": "FullTime"
            },
            ...
          ]
        }
        """
        url = _API_URL.format(company=company_slug)
        response = await client.get(url)

        if response.status_code == 404:
            logger.debug("[Ashby] Company not found: %s", company_slug)
            return []

        response.raise_for_status()
        data = response.json()

        postings = data.get("jobs", [])
        if not isinstance(postings, list):
            logger.warning("[Ashby] Unexpected response format for %s", company_slug)
            return []

        jobs: list[dict] = []
        for posting in postings:
            title = posting.get("title", "")
            location = posting.get("location", "")
            job_url = posting.get("jobUrl", "")

            if not title or not job_url:
                continue

            if not matches_filters(title, location):
                continue

            jobs.append({
                "title": title,
                "company": company_slug.replace("-", " ").title(),
                "url": job_url,
                "location": location,
                "ats_type": "ashby",
            })

        logger.info(
            "[Ashby] %s — %d jobs matched filters (out of %d total)",
            company_slug,
            len(jobs),
            len(postings),
        )
        return jobs
