"""
database.py — SQLite persistence layer for the ATS Job Automator.

Manages the 'offers' table inside jobs_automation.db with:
- Parameterized queries (?) to prevent SQL Injection.
- Indexes on 'url' and 'status' for optimized lookups.
- Exhaustive SQLite exception handling via the logging module.
- Strict status validation: PENDING | APPLIED | FAILED | SKIPPED.
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────────────────
_DB_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = _DB_DIR / "jobs_automation.db"

VALID_STATUSES = frozenset({"PENDING", "APPLIED", "FAILED", "SKIPPED"})

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS offers (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT    NOT NULL,
    job_title    TEXT    NOT NULL,
    url          TEXT    NOT NULL UNIQUE,
    ats_type     TEXT,
    location     TEXT,
    work_modality TEXT,
    status       TEXT    NOT NULL DEFAULT 'PENDING'
                         CHECK (status IN ('PENDING', 'APPLIED', 'FAILED', 'SKIPPED')),
    created_at   TEXT    NOT NULL,
    applied_at   TEXT,
    error_log    TEXT
);
"""

_CREATE_INDEX_URL_SQL = """
CREATE INDEX IF NOT EXISTS idx_offers_url ON offers (url);
"""

_CREATE_INDEX_STATUS_SQL = """
CREATE INDEX IF NOT EXISTS idx_offers_status ON offers (status);
"""

_INSERT_OFFER_SQL = """
INSERT INTO offers (
    company_name, job_title, url, ats_type, location,
    work_modality, status, created_at
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?);
"""

_UPDATE_STATUS_SQL = """
UPDATE offers
   SET status     = ?,
       applied_at = ?,
       error_log  = ?
 WHERE id = ?;
"""


# ─── Database connection helper ──────────────────────────────────────────────
def _get_connection() -> sqlite3.Connection:
    """Open a connection to the SQLite database with recommended pragmas.

    Returns:
        A ``sqlite3.Connection`` with WAL journal mode and foreign keys enabled.

    Raises:
        sqlite3.Error: If the database file cannot be opened or created.
    """
    try:
        _DB_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row  # access columns by name
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        logger.debug("Database connection opened: %s", DB_PATH)
        return conn
    except sqlite3.Error:
        logger.exception("Failed to connect to database at %s", DB_PATH)
        raise


# ─── Public API ──────────────────────────────────────────────────────────────
def init_db() -> None:
    """Initialize the database: create the 'offers' table and indexes.

    Safe to call multiple times — uses IF NOT EXISTS guards.

    Raises:
        sqlite3.Error: If table or index creation fails.
    """
    conn: sqlite3.Connection | None = None
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(_CREATE_TABLE_SQL)
        cursor.execute(_CREATE_INDEX_URL_SQL)
        cursor.execute(_CREATE_INDEX_STATUS_SQL)
        conn.commit()
        logger.info(
            "Database initialized successfully — table 'offers' and indexes ready at %s",
            DB_PATH,
        )
    except sqlite3.OperationalError:
        logger.exception("Operational error while initializing the database schema")
        raise
    except sqlite3.DatabaseError:
        logger.exception("Database error during initialization (possible corruption)")
        raise
    finally:
        if conn is not None:
            conn.close()
            logger.debug("Database connection closed after init_db()")


def insert_offer(
    company_name: str,
    job_title: str,
    url: str,
    ats_type: str | None = None,
    location: str | None = None,
    work_modality: str | None = None,
    status: str = "PENDING",
) -> int | None:
    """Insert a new job offer into the 'offers' table.

    Uses parameterized queries (?) to prevent SQL Injection.

    Args:
        company_name: Name of the hiring company. Required.
        job_title: Title of the position. Required.
        url: Direct URL to the job posting. Required, must be unique.
        ats_type: ATS platform identifier (e.g. 'workday', 'greenhouse').
        location: Job location (e.g. 'Madrid, Spain').
        work_modality: Working arrangement (e.g. 'remote', 'hybrid', 'onsite').
        status: Initial status. Must be one of PENDING, APPLIED, FAILED, SKIPPED.
                Defaults to 'PENDING'.

    Returns:
        The ``id`` (rowid) of the newly inserted offer, or ``None`` if the
        insert failed (e.g. duplicate URL).

    Raises:
        ValueError: If ``status`` is not in the set of valid statuses.
        sqlite3.IntegrityError: If ``url`` already exists in the table.
    """
    if status not in VALID_STATUSES:
        msg = (
            f"Invalid status '{status}'. "
            f"Must be one of: {', '.join(sorted(VALID_STATUSES))}"
        )
        logger.error(msg)
        raise ValueError(msg)

    created_at = datetime.now(timezone.utc).isoformat()
    conn: sqlite3.Connection | None = None

    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(
            _INSERT_OFFER_SQL,
            (company_name, job_title, url, ats_type, location, work_modality, status, created_at),
        )
        conn.commit()
        offer_id = cursor.lastrowid
        logger.info(
            "Offer inserted [id=%s]: '%s' at '%s' (%s)",
            offer_id,
            job_title,
            company_name,
            url,
        )
        return offer_id

    except sqlite3.IntegrityError:
        logger.warning(
            "Duplicate offer skipped — URL already exists: %s",
            url,
        )
        raise
    except sqlite3.OperationalError:
        logger.exception(
            "Operational error inserting offer: '%s' at '%s'",
            job_title,
            company_name,
        )
        raise
    except sqlite3.ProgrammingError:
        logger.exception("Programming error — check SQL or parameter bindings")
        raise
    except sqlite3.DatabaseError:
        logger.exception("Unexpected database error during insert_offer()")
        raise
    finally:
        if conn is not None:
            conn.close()
            logger.debug("Database connection closed after insert_offer()")


def update_offer_status(
    offer_id: int,
    new_status: str,
    error_log: str | None = None,
) -> bool:
    """Update the status of an existing offer.

    Automatically sets ``applied_at`` to the current UTC timestamp when
    the new status is 'APPLIED'.

    Args:
        offer_id: Primary key of the offer to update.
        new_status: Target status. Must be one of PENDING, APPLIED, FAILED, SKIPPED.
        error_log: Optional error message to store (useful for FAILED status).

    Returns:
        ``True`` if exactly one row was updated, ``False`` if no matching
        offer was found.

    Raises:
        ValueError: If ``new_status`` is not in the set of valid statuses.
    """
    if new_status not in VALID_STATUSES:
        msg = (
            f"Invalid status '{new_status}'. "
            f"Must be one of: {', '.join(sorted(VALID_STATUSES))}"
        )
        logger.error(msg)
        raise ValueError(msg)

    applied_at = (
        datetime.now(timezone.utc).isoformat() if new_status == "APPLIED" else None
    )

    conn: sqlite3.Connection | None = None

    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(
            _UPDATE_STATUS_SQL,
            (new_status, applied_at, error_log, offer_id),
        )
        conn.commit()

        if cursor.rowcount == 0:
            logger.warning(
                "No offer found with id=%s — status update skipped",
                offer_id,
            )
            return False

        logger.info(
            "Offer [id=%s] status updated to '%s'%s",
            offer_id,
            new_status,
            f" (error: {error_log})" if error_log else "",
        )
        return True

    except sqlite3.OperationalError:
        logger.exception(
            "Operational error updating offer id=%s to status '%s'",
            offer_id,
            new_status,
        )
        raise
    except sqlite3.DatabaseError:
        logger.exception("Unexpected database error during update_offer_status()")
        raise
    finally:
        if conn is not None:
            conn.close()
            logger.debug("Database connection closed after update_offer_status()")
