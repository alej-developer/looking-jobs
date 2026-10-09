"""Local fit analysis never invents evidence that is not in the profile."""

from src.analysis.fit import analyze_fit


def test_draft_quotes_only_matching_evidence():
    result = analyze_fit(
        {
            "origin_role": "Docente",
            "origin_sector": "Educacion",
            "origin_highlights": "Coordinaba grupos de 20 personas.",
            "bridge": [{"skill": "Python", "evidence": "Curso de 40 horas con un proyecto propio"}],
            "anchors": {"why_change": "Quiero construir producto."},
        },
        {
            "job_title": "Backend Developer",
            "company_name": "Acme",
            "description": "Buscamos Python y Kubernetes en Madrid.",
            "location": "Madrid",
        },
    )
    assert result["fit_score"] == 100
    assert "Curso de 40 horas" in result["draft_body"]
    assert "Kubernetes" not in result["draft_body"]
    assert "Quiero construir producto." in result["draft_body"]


def test_missing_skill_is_a_gap():
    result = analyze_fit(
        {
            "bridge": [{"skill": "SQL", "evidence": "Informes mensuales"}],
            "anchors": {},
        },
        {
            "job_title": "Backend Developer",
            "company_name": "Acme",
            "description": "Experiencia con Python.",
            "location": "Remote",
        },
    )
    assert result["fit_score"] == 0
    assert "SQL" in result["gap_notes"]
    assert "Informes mensuales" not in result["draft_body"]
