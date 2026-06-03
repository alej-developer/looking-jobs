"""
base.py — Abstract base class for ATS application submitters.

Each concrete applicator handles the form-filling and submission
workflow for a specific ATS platform.
"""

from abc import ABC, abstractmethod


class BaseApplicator(ABC):
    """Interface that every ATS applicator must implement."""

    @abstractmethod
    async def fill_application(self, job_url: str, candidate_data: dict) -> bool:
        """Fill out the application form for a given job listing.

        Args:
            job_url: Direct URL to the application page.
            candidate_data: Dict with candidate info (name, email, resume path, etc.).

        Returns:
            True if the form was filled successfully, False otherwise.
        """

    @abstractmethod
    async def submit_application(self, job_url: str) -> bool:
        """Submit a previously filled application.

        Args:
            job_url: Direct URL to the application page.

        Returns:
            True if submission succeeded, False otherwise.
        """
