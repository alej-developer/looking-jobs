"""
job.py — Job listing data model.

Defines the SQLAlchemy ORM model and Pydantic schema for job postings
tracked by the automation pipeline.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, HttpUrl
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


# ─── SQLAlchemy ORM ──────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class JobListing(Base):
    """Represents a single job posting discovered on an ATS portal."""

    __tablename__ = "job_listings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    company = Column(String(300), nullable=False)
    location = Column(String(300), nullable=True)
    url = Column(String(2000), nullable=False, unique=True)
    ats_platform = Column(String(100), nullable=True)  # e.g. "workday", "greenhouse"
    description = Column(Text, nullable=True)
    status = Column(
        String(50), nullable=False, default="discovered"
    )  # discovered | applied | rejected | interview
    discovered_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    applied_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<JobListing(id={self.id}, title='{self.title}', company='{self.company}')>"


# ─── Pydantic Schema ────────────────────────────────────────────────────────
class JobListingSchema(BaseModel):
    """Validation schema for job data entering the system."""

    title: str
    company: str
    location: str | None = None
    url: HttpUrl
    ats_platform: str | None = None
    description: str | None = None

    model_config = {"from_attributes": True}
