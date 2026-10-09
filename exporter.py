"""
exporter.py — Export job offers to CSV and JSON formats.

Exports data from the SQLite database to structured files in the
exports/ directory with timestamped filenames.
"""

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from database import get_all_offers

logger = logging.getLogger(__name__)

_EXPORT_DIR = Path(__file__).resolve().parent / "exports"

_CSV_HEADERS = [
    "id",
    "company_name",
    "job_title",
    "url",
    "ats_type",
    "location",
    "work_modality",
    "status",
    "created_at",
    "applied_at",
    "error_log",
]


def _ensure_export_dir() -> Path:
    """Create the exports directory if it doesn't exist."""
    _EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    return _EXPORT_DIR


def _generate_filename(extension: str, status_filter: str | None = None) -> str:
    """Generate a timestamped filename for the export.

    Args:
        extension: File extension (e.g. 'csv', 'json').
        status_filter: Optional status filter included in filename.

    Returns:
        Filename string like 'offers_2026-06-04_PENDING.csv'.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    suffix = f"_{status_filter}" if status_filter else ""
    return f"offers_{timestamp}{suffix}.{extension}"


def export_csv(status_filter: str | None = None) -> str:
    """Export offers to a CSV file.

    Args:
        status_filter: If provided, only export offers with this status.

    Returns:
        Absolute path to the created CSV file.
    """
    export_dir = _ensure_export_dir()
    filename = _generate_filename("csv", status_filter)
    filepath = export_dir / filename

    offers = get_all_offers(status=status_filter)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_HEADERS, extrasaction="ignore")
        writer.writeheader()
        for offer in offers:
            writer.writerow(offer)

    logger.info("Exported %d offers to CSV: %s", len(offers), filepath)
    return str(filepath)


def export_json(status_filter: str | None = None) -> str:
    """Export offers to a JSON file.

    Args:
        status_filter: If provided, only export offers with this status.

    Returns:
        Absolute path to the created JSON file.
    """
    export_dir = _ensure_export_dir()
    filename = _generate_filename("json", status_filter)
    filepath = export_dir / filename

    offers = get_all_offers(status=status_filter)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(
            {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "total_offers": len(offers),
                "status_filter": status_filter,
                "offers": offers,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    logger.info("Exported %d offers to JSON: %s", len(offers), filepath)
    return str(filepath)
