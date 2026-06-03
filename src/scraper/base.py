"""
base.py — Abstract base class for ATS portal scrapers.

Each concrete scraper (Workday, Greenhouse, Lever, etc.) must inherit
from BaseScraper and implement the abstract methods.
"""

from abc import ABC, abstractmethod


class BaseScraper(ABC):
    """Interface that every ATS scraper must implement."""

    @abstractmethod
    async def search_jobs(self, query: str, location: str = "") -> list[dict]:
        """Search for job listings matching the given query.

        Args:
            query: Job title or keyword search string.
            location: Optional geographic filter.

        Returns:
            A list of dicts, each representing a job listing with at minimum
            the keys: 'title', 'company', 'url', 'location'.
        """

    @abstractmethod
    async def get_job_details(self, job_url: str) -> dict:
        """Fetch full details for a single job listing.

        Args:
            job_url: Direct URL to the job posting on the ATS portal.

        Returns:
            A dict with full job data including 'description', 'requirements',
            'application_url', etc.
        """
