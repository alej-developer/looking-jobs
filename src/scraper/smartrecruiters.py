"""
smartrecruiters.py — Direct API scraper for SmartRecruiters ATS portal.

Endpoint: GET https://api.smartrecruiters.com/v1/companies/{company}/postings
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

_API_URL = "https://api.smartrecruiters.com/v1/companies/{company}/postings"


class SmartRecruitersScraper(BaseScraper):
    """Scraper for SmartRecruiters job board API."""

    async def scrape_all(self) -> list[dict]:
        """Scrape all configured SmartRecruiters companies."""
        companies = get_companies("smartrecruiters")
        all_jobs: list[dict] = []

        logger.info("[SmartRecruiters] Starting scrape for %d companies", len(companies))

        async with create_http_client() as client:
            for slug in companies:
                try:
                    jobs = await self._fetch_company(client, slug)
                    all_jobs.extend(jobs)
                except Exception:
                    logger.exception("[SmartRecruiters] Failed to scrape company: %s", slug)

        logger.info("[SmartRecruiters] Total filtered jobs found: %d", len(all_jobs))
        return all_jobs

    async def scrape_company(self, company_slug: str) -> list[dict]:
        """Scrape jobs from a single SmartRecruiters company."""
        async with create_http_client() as client:
            return await self._fetch_company(client, company_slug)

    async def _fetch_company(self, client, company_slug: str) -> list[dict]:
        """Fetch and filter jobs from one SmartRecruiters company.

        SmartRecruiters API response format:
        {
          "content": [
            {
              "name": "Software Engineer",
              "ref": "https://jobs.smartrecruiters.com/Company/uuid",
              "location": {
                "city": "Madrid",
                "region": "Madrid",
                "country": "Spain"
              },
              "department": {"label": "Engineering"}
            },
            ...
          ]
        }
        """
        url = _API_URL.format(company=company_slug)
        response = await client.get(url)

        if response.status_code == 404:
            logger.debug("[SmartRecruiters] Company not found: %s", company_slug)
            return []

        response.raise_for_status()
        data = response.json()

        postings = data.get("content", [])
        if not isinstance(postings, list):
            logger.warning("[SmartRecruiters] Unexpected response format for %s", company_slug)
            return []

        jobs: list[dict] = []
        for posting in postings:
            title = posting.get("name", "")
            location_obj = posting.get("location", {})
            location_parts = []
            if isinstance(location_obj, dict):
                for key in ("city", "region", "country"):
                    val = location_obj.get(key, "")
                    if val and val not in location_parts:
                        location_parts.append(val)
            location = ", ".join(location_parts)

            job_url = posting.get("ref", "")

            if not title or not job_url:
                continue

            if not matches_filters(title, location):
                continue

            jobs.append({
                "title": title,
                "company": company_slug.replace("-", " ").title(),
                "url": job_url,
                "location": location,
                "ats_type": "smartrecruiters",
            })

        logger.info(
            "[SmartRecruiters] %s — %d jobs matched filters (out of %d total)",
            company_slug,
            len(jobs),
            len(postings),
        )
        return jobs
