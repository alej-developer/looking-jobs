"""
database.py — SQLite persistence layer for the ATS Job Automator.

Manages the 'offers' table inside jobs_automation.db with:
- Parameterized queries (?) to prevent SQL Injection.
- Indexes on 'url' and 'status' for optimized lookups.
- Exhaustive SQLite exception handling via the logging module.
- Strict status validation: PENDING | DRAFT | APPLIED | INTERVIEW |
  REJECTED | OFFER | SKIPPED | FAILED.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────────────────
_DB_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = _DB_DIR / "jobs_automation.db"

VALID_STATUSES = frozenset({
    "PENDING",
    "DRAFT",
    "APPLIED",
    "INTERVIEW",
    "REJECTED",
    "OFFER",
    "SKIPPED",
    "FAILED",
})

_OFFER_COLUMNS = (
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
    "description",
    "fit_score",
    "fit_summary",
    "gap_notes",
    "draft_body",
)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS offers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name  TEXT    NOT NULL,
    job_title     TEXT    NOT NULL,
    url           TEXT    NOT NULL UNIQUE,
    ats_type      TEXT,
    location      TEXT,
    work_modality TEXT,
    status        TEXT    NOT NULL DEFAULT 'PENDING'
                          CHECK (status IN (
                              'PENDING', 'DRAFT', 'APPLIED', 'INTERVIEW',
                              'REJECTED', 'OFFER', 'SKIPPED', 'FAILED'
                          )),
    created_at    TEXT    NOT NULL,
    applied_at    TEXT,
    error_log     TEXT,
    description   TEXT,
    fit_score     INTEGER,
    fit_summary   TEXT,
    gap_notes     TEXT,
    draft_body    TEXT
);
"""

_CREATE_PROFILE_SQL = """
CREATE TABLE IF NOT EXISTS candidate_profile (
    id                INTEGER PRIMARY KEY CHECK (id = 1),
    full_name         TEXT NOT NULL DEFAULT '',
    email             TEXT NOT NULL DEFAULT '',
    phone             TEXT NOT NULL DEFAULT '',
    origin_sector     TEXT NOT NULL DEFAULT '',
    origin_role       TEXT NOT NULL DEFAULT '',
    origin_years      INTEGER,
    origin_highlights TEXT NOT NULL DEFAULT '',
    target_roles      TEXT NOT NULL DEFAULT '',
    target_sectors    TEXT NOT NULL DEFAULT '',
    seniority         TEXT NOT NULL DEFAULT '',
    constraints_text  TEXT NOT NULL DEFAULT '',
    bridge_json       TEXT NOT NULL DEFAULT '[]',
    anchors_json      TEXT NOT NULL DEFAULT '{}',
    proof_json        TEXT NOT NULL DEFAULT '[]',
    updated_at        TEXT NOT NULL
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
    work_modality, status, created_at, description
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

_UPDATE_STATUS_SQL = """
UPDATE offers
   SET status     = ?,
       applied_at = ?,
       error_log  = ?
 WHERE id = ?;
"""

_SELECT_LIST = ", ".join(_OFFER_COLUMNS)

_SELECT_ALL_SQL = f"""
SELECT {_SELECT_LIST}
  FROM offers
 {{where_clause}}
 ORDER BY created_at DESC
"""

_SELECT_BY_URL_SQL = f"""
SELECT {_SELECT_LIST}
  FROM offers
 WHERE url = ?;
"""

_SELECT_BY_ID_SQL = f"""
SELECT {_SELECT_LIST}
  FROM offers
 WHERE id = ?;
"""

_COUNT_SQL = """
SELECT COUNT(*) AS count
  FROM offers
 {where_clause}
"""

_SUMMARY_SQL = """
SELECT status, COUNT(*) as count
  FROM offers
 GROUP BY status;
"""

_DELETE_OFFER_SQL = """
DELETE FROM offers WHERE id = ?;
"""


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
def _ensure_offers_schema(conn: sqlite3.Connection) -> None:
    """Create or rebuild the offers table so new columns and statuses exist.

    Column names interpolated into SQL come only from a fixed allow-list
    intersected with the live table definition, never from user input.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'offers'"
    ).fetchone()
    if row is None:
        conn.execute(_CREATE_TABLE_SQL)
        return

    current_sql = row[0] or ""
    if "DRAFT" in current_sql and "fit_score" in current_sql:
        return

    conn.execute("ALTER TABLE offers RENAME TO offers_legacy")
    conn.execute(_CREATE_TABLE_SQL)
    legacy_cols = {info[1] for info in conn.execute("PRAGMA table_info(offers_legacy)")}
    required = {
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
    }
    if not required.issubset(legacy_cols):
        raise sqlite3.DatabaseError("legacy offers table is missing required columns")
    conn.execute(
        """
        INSERT INTO offers (
            id, company_name, job_title, url, ats_type, location,
            work_modality, status, created_at, applied_at, error_log
        )
        SELECT
            id, company_name, job_title, url, ats_type, location,
            work_modality, status, created_at, applied_at, error_log
        FROM offers_legacy
        """
    )
    conn.execute("DROP TABLE offers_legacy")


def init_db() -> None:
    """Initialize the database: create the 'offers' table and indexes.

    Safe to call multiple times — uses IF NOT EXISTS guards and a rebuild
    migration when an older offers schema is already present.

    Raises:
        sqlite3.Error: If table or index creation fails.
    """
    conn: sqlite3.Connection | None = None
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        _ensure_offers_schema(conn)
        cursor.execute(_CREATE_PROFILE_SQL)
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
    description: str | None = None,
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
            (
                company_name,
                job_title,
                url,
                ats_type,
                location,
                work_modality,
                status,
                created_at,
                description,
            ),
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


def get_all_offers(status: str | None = None) -> list[dict]:
    """Retrieve all offers, optionally filtered by status.

    Args:
        status: If provided, only return offers with this status.
                Must be one of PENDING, APPLIED, FAILED, SKIPPED.

    Returns:
        A list of dicts, each representing one row from the offers table.
    """
    if status is not None and status not in VALID_STATUSES:
        msg = (
            f"Invalid status filter '{status}'. "
            f"Must be one of: {', '.join(sorted(VALID_STATUSES))}"
        )
        logger.error(msg)
        raise ValueError(msg)

    conn: sqlite3.Connection | None = None
    try:
        conn = _get_connection()
        if status:
            query = _SELECT_ALL_SQL.format(where_clause="WHERE status = ?")
            rows = conn.execute(query, (status,)).fetchall()
        else:
            query = _SELECT_ALL_SQL.format(where_clause="")
            rows = conn.execute(query).fetchall()

        results = [dict(row) for row in rows]
        logger.debug("Retrieved %d offers (filter=%s)", len(results), status)
        return results

    except sqlite3.DatabaseError:
        logger.exception("Error retrieving offers")
        raise
    finally:
        if conn is not None:
            conn.close()


def get_offer_by_url(url: str) -> dict | None:
    """Look up a single offer by its URL.

    Useful for deduplication checks before inserting.

    Args:
        url: The job posting URL to search for.

    Returns:
        A dict with the offer data, or None if not found.
    """
    conn: sqlite3.Connection | None = None
    try:
        conn = _get_connection()
        row = conn.execute(_SELECT_BY_URL_SQL, (url,)).fetchone()
        if row:
            return dict(row)
        return None

    except sqlite3.DatabaseError:
        logger.exception("Error looking up offer by URL: %s", url)
        raise
    finally:
        if conn is not None:
            conn.close()


def get_offers_summary() -> dict[str, int]:
    """Get a count of offers grouped by status.

    Returns:
        A dict like ``{"PENDING": 12, "APPLIED": 3, "FAILED": 1, "SKIPPED": 0}``.
        Statuses with zero offers are included with a count of 0.
    """
    conn: sqlite3.Connection | None = None
    try:
        conn = _get_connection()
        rows = conn.execute(_SUMMARY_SQL).fetchall()
        summary = {s: 0 for s in sorted(VALID_STATUSES)}
        for row in rows:
            summary[row["status"]] = row["count"]

        logger.debug("Offers summary: %s", summary)
        return summary

    except sqlite3.DatabaseError:
        logger.exception("Error generating offers summary")
        raise
    finally:
        if conn is not None:
            conn.close()


def delete_offer(offer_id: int) -> bool:
    """Delete an offer by its ID.

    Args:
        offer_id: Primary key of the offer to delete.

    Returns:
        True if the offer was deleted, False if no matching offer was found.
    """
    conn: sqlite3.Connection | None = None
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(_DELETE_OFFER_SQL, (offer_id,))
        conn.commit()

        if cursor.rowcount == 0:
            logger.warning("No offer found with id=%s — delete skipped", offer_id)
            return False

        logger.info("Offer [id=%s] deleted", offer_id)
        return True

    except sqlite3.DatabaseError:
        logger.exception("Error deleting offer id=%s", offer_id)
        raise
    finally:
        if conn is not None:
            conn.close()


def get_offer_by_id(offer_id: int) -> dict | None:
    """Return one offer by primary key, or None when it does not exist."""
    conn: sqlite3.Connection | None = None
    try:
        conn = _get_connection()
        row = conn.execute(_SELECT_BY_ID_SQL, (offer_id,)).fetchone()
        return dict(row) if row else None
    except sqlite3.DatabaseError:
        logger.exception("Error looking up offer id=%s", offer_id)
        raise
    finally:
        if conn is not None:
            conn.close()


def list_offers(
    status: str | None = None,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Return a page of offers and the total count for that filter."""
    if status is not None and status not in VALID_STATUSES:
        msg = (
            f"Invalid status filter '{status}'. "
            f"Must be one of: {', '.join(sorted(VALID_STATUSES))}"
        )
        logger.error(msg)
        raise ValueError(msg)

    bounded_limit = min(max(int(limit), 1), 100)
    bounded_offset = max(int(offset), 0)
    where = "WHERE status = ?" if status else ""
    params: tuple = (status,) if status else ()

    conn: sqlite3.Connection | None = None
    try:
        conn = _get_connection()
        total = conn.execute(
            _COUNT_SQL.format(where_clause=where),
            params,
        ).fetchone()["count"]
        rows = conn.execute(
            _SELECT_ALL_SQL.format(where_clause=where) + " LIMIT ? OFFSET ?",
            (*params, bounded_limit, bounded_offset),
        ).fetchall()
        return [dict(row) for row in rows], int(total)
    except sqlite3.DatabaseError:
        logger.exception("Error listing offers")
        raise
    finally:
        if conn is not None:
            conn.close()


def update_offer_draft(offer_id: int, draft_body: str | None) -> bool:
    """Replace the user-edited draft stored on an offer."""
    conn: sqlite3.Connection | None = None
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE offers SET draft_body = ? WHERE id = ?",
            (draft_body, offer_id),
        )
        conn.commit()
        return cursor.rowcount == 1
    except sqlite3.DatabaseError:
        logger.exception("Error updating draft for offer id=%s", offer_id)
        raise
    finally:
        if conn is not None:
            conn.close()


def save_offer_analysis(
    offer_id: int,
    *,
    fit_score: int,
    fit_summary: str,
    gap_notes: str,
    draft_body: str,
) -> bool:
    """Persist a locally computed fit analysis. Does not change status."""
    conn: sqlite3.Connection | None = None
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE offers
               SET fit_score = ?,
                   fit_summary = ?,
                   gap_notes = ?,
                   draft_body = ?
             WHERE id = ?
            """,
            (fit_score, fit_summary, gap_notes, draft_body, offer_id),
        )
        conn.commit()
        return cursor.rowcount == 1
    except sqlite3.DatabaseError:
        logger.exception("Error saving analysis for offer id=%s", offer_id)
        raise
    finally:
        if conn is not None:
            conn.close()


_PROFILE_DEFAULTS: dict = {
    "full_name": "",
    "email": "",
    "phone": "",
    "origin_sector": "",
    "origin_role": "",
    "origin_years": None,
    "origin_highlights": "",
    "target_roles": "",
    "target_sectors": "",
    "seniority": "",
    "constraints_text": "",
    "bridge": [],
    "anchors": {},
    "proof": [],
    "updated_at": "",
}


def _profile_from_row(row: sqlite3.Row) -> dict:
    """Decode a profile row. Corrupt JSON becomes empty collections."""
    data = dict(_PROFILE_DEFAULTS)
    skip = {"bridge", "anchors", "proof"}
    present = {
        key: row[key]
        for key in row.keys()
        if key in data and key not in skip
    }
    data.update(present)
    for column, fallback in (("bridge_json", []), ("anchors_json", {}), ("proof_json", [])):
        target = column.removesuffix("_json")
        try:
            parsed = json.loads(row[column] or "")
        except json.JSONDecodeError:
            parsed = fallback
        if isinstance(parsed, type(fallback)):
            data[target] = parsed
        else:
            data[target] = fallback
    return data


def get_profile() -> dict:
    """Return the singleton candidate profile, or defaults when unset."""
    conn: sqlite3.Connection | None = None
    try:
        conn = _get_connection()
        row = conn.execute("SELECT * FROM candidate_profile WHERE id = 1").fetchone()
        if row is None:
            return dict(_PROFILE_DEFAULTS)
        return _profile_from_row(row)
    except sqlite3.DatabaseError:
        logger.exception("Error reading candidate profile")
        raise
    finally:
        if conn is not None:
            conn.close()


def save_profile(payload: dict) -> dict:
    """Insert or replace the singleton profile. Caller must already validate fields."""
    updated_at = datetime.now(timezone.utc).isoformat()
    record = {
        "full_name": payload.get("full_name", ""),
        "email": payload.get("email", ""),
        "phone": payload.get("phone", ""),
        "origin_sector": payload.get("origin_sector", ""),
        "origin_role": payload.get("origin_role", ""),
        "origin_years": payload.get("origin_years"),
        "origin_highlights": payload.get("origin_highlights", ""),
        "target_roles": payload.get("target_roles", ""),
        "target_sectors": payload.get("target_sectors", ""),
        "seniority": payload.get("seniority", ""),
        "constraints_text": payload.get("constraints_text", ""),
        "bridge_json": json.dumps(payload.get("bridge", []), ensure_ascii=False),
        "anchors_json": json.dumps(payload.get("anchors", {}), ensure_ascii=False),
        "proof_json": json.dumps(payload.get("proof", []), ensure_ascii=False),
        "updated_at": updated_at,
    }
    conn: sqlite3.Connection | None = None
    try:
        conn = _get_connection()
        conn.execute(
            """
            INSERT INTO candidate_profile (
                id, full_name, email, phone, origin_sector, origin_role, origin_years,
                origin_highlights, target_roles, target_sectors, seniority,
                constraints_text, bridge_json, anchors_json, proof_json, updated_at
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                full_name = excluded.full_name,
                email = excluded.email,
                phone = excluded.phone,
                origin_sector = excluded.origin_sector,
                origin_role = excluded.origin_role,
                origin_years = excluded.origin_years,
                origin_highlights = excluded.origin_highlights,
                target_roles = excluded.target_roles,
                target_sectors = excluded.target_sectors,
                seniority = excluded.seniority,
                constraints_text = excluded.constraints_text,
                bridge_json = excluded.bridge_json,
                anchors_json = excluded.anchors_json,
                proof_json = excluded.proof_json,
                updated_at = excluded.updated_at
            """,
            (
                record["full_name"],
                record["email"],
                record["phone"],
                record["origin_sector"],
                record["origin_role"],
                record["origin_years"],
                record["origin_highlights"],
                record["target_roles"],
                record["target_sectors"],
                record["seniority"],
                record["constraints_text"],
                record["bridge_json"],
                record["anchors_json"],
                record["proof_json"],
                record["updated_at"],
            ),
        )
        conn.commit()
        return get_profile()
    except sqlite3.DatabaseError:
        logger.exception("Error saving candidate profile")
        raise
    finally:
        if conn is not None:
            conn.close()
