"""Tests for the database module — CRUD operations and data integrity."""

import os
import sqlite3
import tempfile

import pytest

# Patch DB path before importing database module
_test_db_dir = tempfile.mkdtemp()
_test_db_path = os.path.join(_test_db_dir, "test_jobs.db")


@pytest.fixture(autouse=True)
def _patch_db(monkeypatch):
    """Redirect database to a temporary file for each test."""
    import database
    from pathlib import Path

    monkeypatch.setattr(database, "DB_PATH", Path(_test_db_path))
    monkeypatch.setattr(database, "_DB_DIR", Path(_test_db_dir))

    # Clean slate for each test
    if os.path.exists(_test_db_path):
        os.remove(_test_db_path)

    database.init_db()
    yield

    if os.path.exists(_test_db_path):
        os.remove(_test_db_path)


class TestInitDb:
    """Tests for init_db()."""

    def test_creates_table(self):
        """init_db should create the offers table."""
        from database import DB_PATH
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='offers'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_creates_indexes(self):
        """init_db should create indexes on url and status."""
        from database import DB_PATH
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
        index_names = [row[0] for row in cursor.fetchall()]
        assert "idx_offers_url" in index_names
        assert "idx_offers_status" in index_names
        conn.close()

    def test_idempotent(self):
        """init_db should be safe to call multiple times."""
        from database import init_db
        init_db()
        init_db()  # Should not raise


class TestInsertOffer:
    """Tests for insert_offer()."""

    def test_insert_returns_id(self):
        from database import insert_offer
        offer_id = insert_offer(
            company_name="TestCo",
            job_title="Python Developer",
            url="https://example.com/job/1",
        )
        assert offer_id is not None
        assert isinstance(offer_id, int)

    def test_duplicate_url_raises(self):
        from database import insert_offer
        insert_offer(
            company_name="TestCo",
            job_title="Python Developer",
            url="https://example.com/job/dup",
        )
        with pytest.raises(sqlite3.IntegrityError):
            insert_offer(
                company_name="OtherCo",
                job_title="Another Role",
                url="https://example.com/job/dup",
            )

    def test_invalid_status_raises(self):
        from database import insert_offer
        with pytest.raises(ValueError, match="Invalid status"):
            insert_offer(
                company_name="TestCo",
                job_title="Dev",
                url="https://example.com/job/bad",
                status="INVALID",
            )

    def test_all_valid_statuses(self):
        from database import insert_offer, VALID_STATUSES
        for i, status in enumerate(sorted(VALID_STATUSES)):
            offer_id = insert_offer(
                company_name="TestCo",
                job_title=f"Dev {status}",
                url=f"https://example.com/job/status-{i}",
                status=status,
            )
            assert offer_id is not None


class TestUpdateOfferStatus:
    """Tests for update_offer_status()."""

    def test_update_to_applied(self):
        from database import insert_offer, update_offer_status, get_all_offers
        offer_id = insert_offer(
            company_name="TestCo",
            job_title="Dev",
            url="https://example.com/job/update",
        )
        result = update_offer_status(offer_id, "APPLIED")
        assert result is True

        offers = get_all_offers()
        offer = next(o for o in offers if o["id"] == offer_id)
        assert offer["status"] == "APPLIED"
        assert offer["applied_at"] is not None

    def test_update_nonexistent_returns_false(self):
        from database import update_offer_status
        result = update_offer_status(99999, "APPLIED")
        assert result is False

    def test_update_invalid_status_raises(self):
        from database import insert_offer, update_offer_status
        offer_id = insert_offer(
            company_name="TestCo",
            job_title="Dev",
            url="https://example.com/job/invalid-update",
        )
        with pytest.raises(ValueError, match="Invalid status"):
            update_offer_status(offer_id, "NOT_A_STATUS")


class TestGetAllOffers:
    """Tests for get_all_offers()."""

    def test_returns_empty_list(self):
        from database import get_all_offers
        offers = get_all_offers()
        assert offers == []

    def test_returns_all_offers(self):
        from database import insert_offer, get_all_offers
        for i in range(3):
            insert_offer(
                company_name="TestCo",
                job_title=f"Dev {i}",
                url=f"https://example.com/job/{i}",
            )
        offers = get_all_offers()
        assert len(offers) == 3

    def test_filters_by_status(self):
        from database import insert_offer, update_offer_status, get_all_offers
        id1 = insert_offer(
            company_name="Co1", job_title="Dev1", url="https://example.com/f1",
        )
        insert_offer(
            company_name="Co2", job_title="Dev2", url="https://example.com/f2",
        )
        update_offer_status(id1, "APPLIED")

        pending = get_all_offers(status="PENDING")
        applied = get_all_offers(status="APPLIED")
        assert len(pending) == 1
        assert len(applied) == 1

    def test_invalid_filter_raises(self):
        from database import get_all_offers
        with pytest.raises(ValueError, match="Invalid status"):
            get_all_offers(status="BADSTATUS")


class TestGetOfferByUrl:
    """Tests for get_offer_by_url()."""

    def test_found(self):
        from database import insert_offer, get_offer_by_url
        insert_offer(
            company_name="TestCo", job_title="Dev", url="https://example.com/findme",
        )
        offer = get_offer_by_url("https://example.com/findme")
        assert offer is not None
        assert offer["job_title"] == "Dev"

    def test_not_found(self):
        from database import get_offer_by_url
        offer = get_offer_by_url("https://example.com/nonexistent")
        assert offer is None


class TestGetOffersSummary:
    """Tests for get_offers_summary()."""

    def test_empty_db(self):
        from database import get_offers_summary
        summary = get_offers_summary()
        assert all(v == 0 for v in summary.values())

    def test_with_offers(self):
        from database import insert_offer, update_offer_status, get_offers_summary
        id1 = insert_offer(
            company_name="Co1", job_title="D1", url="https://example.com/s1",
        )
        insert_offer(
            company_name="Co2", job_title="D2", url="https://example.com/s2",
        )
        update_offer_status(id1, "APPLIED")

        summary = get_offers_summary()
        assert summary["PENDING"] == 1
        assert summary["APPLIED"] == 1


class TestDeleteOffer:
    """Tests for delete_offer()."""

    def test_delete_existing(self):
        from database import insert_offer, delete_offer, get_all_offers
        offer_id = insert_offer(
            company_name="TestCo", job_title="Dev", url="https://example.com/del",
        )
        result = delete_offer(offer_id)
        assert result is True
        assert len(get_all_offers()) == 0

    def test_delete_nonexistent(self):
        from database import delete_offer
        result = delete_offer(99999)
        assert result is False
