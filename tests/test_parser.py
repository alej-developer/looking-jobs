"""Tests for the parser module — regex classification engine."""

import pytest

from parser import classify_job


class TestWorkModality:
    """Tests for work modality classification (REMOTE, HYBRID, ON_SITE)."""

    def test_remote_english(self):
        result = classify_job("Python Developer - Remote", "https://lever.co/job")
        assert result.work_modality == "REMOTE"

    def test_remote_spanish(self):
        result = classify_job("Desarrollador Python - Teletrabajo", "https://lever.co/job")
        assert result.work_modality == "REMOTE"

    def test_hybrid_english(self):
        result = classify_job("Fullstack Engineer - Hybrid", "https://lever.co/job")
        assert result.work_modality == "HYBRID"

    def test_hybrid_spanish(self):
        result = classify_job("Developer Python - Hibrido Madrid", "https://lever.co/job")
        assert result.work_modality == "HYBRID"

    def test_on_site_default(self):
        result = classify_job("Software Engineer", "https://lever.co/job")
        assert result.work_modality == "UNKNOWN"

    def test_remote_in_url(self):
        result = classify_job(
            "Developer",
            "https://lever.co/company/remote-python-developer"
        )
        assert result.work_modality == "REMOTE"

    def test_remote_priority_over_hybrid(self):
        """REMOTE should take priority when both keywords are present."""
        result = classify_job("Remote/Hybrid Developer", "https://lever.co/job")
        assert result.work_modality == "REMOTE"


class TestGeoScope:
    """Tests for geographic scope classification (SPAIN, INTERNATIONAL)."""

    def test_spain_madrid(self):
        result = classify_job("Python Developer Remote Madrid", "https://lever.co/job")
        assert result.geo_scope == "SPAIN"

    def test_spain_barcelona(self):
        result = classify_job("Developer Barcelona", "https://lever.co/job")
        assert result.geo_scope == "SPAIN"

    def test_spain_keyword(self):
        result = classify_job("Remote Python - Spain", "https://lever.co/job")
        assert result.geo_scope == "SPAIN"

    def test_international_worldwide(self):
        result = classify_job("Engineer - Worldwide", "https://lever.co/job")
        assert result.geo_scope == "INTERNATIONAL"

    def test_international_global(self):
        result = classify_job("Developer - Global Remote", "https://lever.co/job")
        assert result.geo_scope == "INTERNATIONAL"

    def test_unknown_geo(self):
        result = classify_job("Generic Developer", "https://lever.co/job")
        assert result.geo_scope == "UNKNOWN"


class TestClassifyJobReturnType:
    """Tests for the JobClassification dataclass."""

    def test_returns_frozen_dataclass(self):
        result = classify_job("Python Dev - Remote", "https://lever.co/job")
        # Should be frozen (immutable)
        with pytest.raises(AttributeError):
            result.work_modality = "HYBRID"

    def test_has_required_fields(self):
        result = classify_job("Dev", "https://lever.co/job")
        assert hasattr(result, "work_modality")
        assert hasattr(result, "geo_scope")
        assert hasattr(result, "geo_match")


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_title(self):
        result = classify_job("", "https://lever.co/remote")
        # Should not crash
        assert result.work_modality in ("REMOTE", "HYBRID", "ON_SITE")

    def test_empty_url(self):
        result = classify_job("Python Developer Remote", "")
        assert result.work_modality == "REMOTE"

    def test_case_insensitive_keywords(self):
        result = classify_job("REMOTE PYTHON DEVELOPER", "https://lever.co/job")
        assert result.work_modality == "REMOTE"
