"""Tests for the loopback API. The token used here is a fixture, not a secret."""

import sqlite3

import pytest

TOKEN = "t" * 32
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def client(monkeypatch, tmp_path):
    """API client pointed at a temporary database and a test token."""
    import database

    monkeypatch.setattr(database, "DB_PATH", tmp_path / "api.db")
    monkeypatch.setattr(database, "_DB_DIR", tmp_path)
    monkeypatch.setenv("API_TOKEN", TOKEN)

    from fastapi.testclient import TestClient

    from src.api.app import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


def test_offers_require_auth(client):
    response = client.get("/api/offers")
    assert response.status_code == 401
    assert "token" not in response.text.lower()


def test_list_and_import_offer(client):
    created = client.post(
        "/api/offers/import",
        headers=AUTH,
        json={
            "company_name": "Acme",
            "job_title": "Backend Developer",
            "url": "https://example.com/jobs/1",
            "description": "<p>Python</p> and SQL",
            "location": "Madrid",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert "<p>" not in body["description"]
    assert "Python" in body["description"]
    assert "resume" not in body

    listing = client.get("/api/offers", headers=AUTH)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1


def test_rejects_credential_url(client):
    response = client.post(
        "/api/offers/import",
        headers=AUTH,
        json={
            "company_name": "Acme",
            "job_title": "Backend Developer",
            "url": "https://user:secret@example.com/jobs/1",
        },
    )
    assert response.status_code == 422
    assert "secret" not in response.text


def test_profile_roundtrip_has_no_filesystem_path(client):
    payload = {
        "full_name": "Ada Lovelace",
        "email": "ada@example.com",
        "origin_sector": "Research",
        "origin_role": "Analyst",
        "origin_years": 4,
        "bridge": [{"skill": "Python", "evidence": "Built data pipelines"}],
        "anchors": {"why_change": "Moving into product engineering"},
        "proof": ["Open source contribution"],
    }
    saved = client.put("/api/profile", headers=AUTH, json=payload)
    assert saved.status_code == 200
    body = saved.json()
    assert body["full_name"] == "Ada Lovelace"
    assert body["bridge"][0]["skill"] == "Python"
    assert "resume_file" not in body
    assert "\\" not in response_text(body)


def test_login_cookie_is_http_only_and_not_the_token(client):
    response = client.post("/api/auth/login", json={"token": TOKEN})
    assert response.status_code == 200
    set_cookie = response.headers["set-cookie"].lower()
    assert "httponly" in set_cookie
    assert "samesite=strict" in set_cookie
    assert TOKEN not in response.headers["set-cookie"]
    me = client.get("/api/me")
    assert me.status_code == 200


def test_wrong_token_is_not_echoed(client):
    leaked = "this-value-must-not-leak-999"
    response = client.post("/api/auth/login", json={"token": leaked})
    assert response.status_code == 401
    assert leaked not in response.text


def test_patch_status(client):
    created = client.post(
        "/api/offers/import",
        headers=AUTH,
        json={
            "company_name": "Acme",
            "job_title": "Backend Developer",
            "url": "https://example.com/jobs/2",
        },
    )
    offer_id = created.json()["id"]
    patched = client.patch(
        f"/api/offers/{offer_id}",
        headers=AUTH,
        json={"status": "INTERVIEW", "draft_body": "Borrador revisado"},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "INTERVIEW"
    assert patched.json()["draft_body"] == "Borrador revisado"


def test_analyze_uses_profile_evidence_only(client):
    client.put(
        "/api/profile",
        headers=AUTH,
        json={
            "origin_role": "Analista",
            "origin_sector": "Investigacion",
            "bridge": [{"skill": "Python", "evidence": "Pipeline interno"}],
        },
    )
    created = client.post(
        "/api/offers/import",
        headers=AUTH,
        json={
            "company_name": "Acme",
            "job_title": "Backend Developer",
            "url": "https://example.com/jobs/3",
            "description": "Python y algo de Go",
        },
    )
    offer_id = created.json()["id"]
    analyzed = client.post(f"/api/offers/{offer_id}/analyze", headers=AUTH)
    assert analyzed.status_code == 200
    body = analyzed.json()
    assert body["fit_score"] == 100
    assert "Pipeline interno" in body["draft_body"]
    assert "Go" not in body["draft_body"]


def test_server_refuses_non_loopback(monkeypatch):
    monkeypatch.setattr("src.api.server.API_HOST", "0.0.0.0")
    monkeypatch.setenv("API_TOKEN", TOKEN)
    from src.api.server import assert_server_config

    with pytest.raises(SystemExit):
        assert_server_config()


def test_server_refuses_short_token(monkeypatch):
    monkeypatch.setattr("src.api.server.API_HOST", "127.0.0.1")
    monkeypatch.setenv("API_TOKEN", "short")
    from src.api.server import assert_server_config

    with pytest.raises(SystemExit):
        assert_server_config()


def test_legacy_offers_table_is_migrated(tmp_path, monkeypatch):
    import database

    db_path = tmp_path / "legacy.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)
    monkeypatch.setattr(database, "_DB_DIR", tmp_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            job_title TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            ats_type TEXT,
            location TEXT,
            work_modality TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING'
                CHECK (status IN ('PENDING', 'APPLIED', 'FAILED', 'SKIPPED')),
            created_at TEXT NOT NULL,
            applied_at TEXT,
            error_log TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO offers (company_name, job_title, url, status, created_at)
        VALUES ('Co', 'Dev', 'https://example.com/legacy', 'PENDING', '2020-01-01T00:00:00+00:00')
        """
    )
    conn.commit()
    conn.close()

    database.init_db()
    offer = database.get_offer_by_url("https://example.com/legacy")
    assert offer is not None
    assert offer["fit_score"] is None
    sql = sqlite3.connect(db_path).execute(
        "SELECT sql FROM sqlite_master WHERE name = 'offers'"
    ).fetchone()[0]
    assert "INTERVIEW" in sql


def response_text(body: dict) -> str:
    return str(body)
