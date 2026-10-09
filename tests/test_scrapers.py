"""Tests for the scraper filter logic in src/scraper/base.py."""

import json

import pytest


@pytest.fixture(autouse=True)
def _patch_config(monkeypatch, tmp_path):
    """Create a test companies.json and patch the config loader."""
    import src.scraper.base as base_module

    test_config = {
        "lever": ["testcompany"],
        "greenhouse": ["testco2"],
        "keywords_include": [
            "python", "fullstack", "backend", "developer", "engineer"
        ],
        "keywords_exclude_seniority": [
            "senior", "sr.", "staff", "principal", "lead",
            "architect", "director", "head of"
        ],
        "locations": [
            "spain", "remote", "madrid", "barcelona", "europe"
        ],
    }

    config_path = tmp_path / "companies.json"
    config_path.write_text(json.dumps(test_config), encoding="utf-8")

    monkeypatch.setattr(base_module, "_COMPANIES_FILE", config_path)
    monkeypatch.setattr(base_module, "_config_cache", None)
    yield


class TestMatchesFilters:
    """Tests for the matches_filters() function."""

    def test_matches_python_remote(self):
        from src.scraper.base import matches_filters
        assert matches_filters("Python Developer", "Remote") is True

    def test_matches_fullstack_spain(self):
        from src.scraper.base import matches_filters
        assert matches_filters("Fullstack Engineer", "Madrid, Spain") is True

    def test_matches_backend_europe(self):
        from src.scraper.base import matches_filters
        assert matches_filters("Backend Developer", "Europe") is True

    def test_rejects_no_keyword_match(self):
        from src.scraper.base import matches_filters
        assert matches_filters("Marketing Manager", "Remote") is False

    def test_rejects_senior(self):
        from src.scraper.base import matches_filters
        assert matches_filters("Senior Python Developer", "Remote") is False

    def test_rejects_staff(self):
        from src.scraper.base import matches_filters
        assert matches_filters("Staff Engineer", "Madrid") is False

    def test_rejects_principal(self):
        from src.scraper.base import matches_filters
        assert matches_filters("Principal Software Engineer", "Remote") is False

    def test_rejects_lead(self):
        from src.scraper.base import matches_filters
        assert matches_filters("Lead Python Developer", "Spain") is False

    def test_rejects_architect(self):
        from src.scraper.base import matches_filters
        assert matches_filters("Software Architect", "Remote") is False

    def test_rejects_director(self):
        from src.scraper.base import matches_filters
        assert matches_filters("Director of Engineering", "Madrid") is False

    def test_rejects_head_of(self):
        from src.scraper.base import matches_filters
        assert matches_filters("Head of Backend", "Barcelona") is False

    def test_rejects_wrong_location(self):
        from src.scraper.base import matches_filters
        assert matches_filters("Python Developer", "New York, USA") is False

    def test_no_location_passes(self):
        """Jobs with no location data should pass location filter."""
        from src.scraper.base import matches_filters
        assert matches_filters("Python Developer", "") is True

    def test_case_insensitive_title(self):
        from src.scraper.base import matches_filters
        assert matches_filters("PYTHON DEVELOPER", "remote") is True

    def test_case_insensitive_location(self):
        from src.scraper.base import matches_filters
        assert matches_filters("Fullstack Developer", "MADRID") is True


class TestGetCompanies:
    """Tests for get_companies()."""

    def test_returns_lever_companies(self):
        from src.scraper.base import get_companies
        companies = get_companies("lever")
        assert companies == ["testcompany"]

    def test_returns_empty_for_unknown(self):
        from src.scraper.base import get_companies
        companies = get_companies("unknown_platform")
        assert companies == []


class TestGetKeywords:
    """Tests for keyword getter functions."""

    def test_include_keywords(self):
        from src.scraper.base import get_keywords_include
        keywords = get_keywords_include()
        assert "python" in keywords
        assert "fullstack" in keywords

    def test_exclude_keywords(self):
        from src.scraper.base import get_keywords_exclude
        keywords = get_keywords_exclude()
        assert "senior" in keywords
        assert "staff" in keywords
        assert "lead" in keywords
