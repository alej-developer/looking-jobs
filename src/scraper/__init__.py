"""ATS scraper implementations."""

from src.scraper.ashby import AshbyScraper
from src.scraper.greenhouse import GreenhouseScraper
from src.scraper.lever import LeverScraper
from src.scraper.recruitee import RecruiteeScraper
from src.scraper.smartrecruiters import SmartRecruitersScraper
from src.scraper.workable import WorkableScraper

ALL_SCRAPERS = {
    "lever": LeverScraper,
    "greenhouse": GreenhouseScraper,
    "ashby": AshbyScraper,
    "smartrecruiters": SmartRecruitersScraper,
    "recruitee": RecruiteeScraper,
    "workable": WorkableScraper,
}

__all__ = [
    "LeverScraper",
    "GreenhouseScraper",
    "AshbyScraper",
    "SmartRecruitersScraper",
    "RecruiteeScraper",
    "WorkableScraper",
    "ALL_SCRAPERS",
]
