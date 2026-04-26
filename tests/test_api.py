"""Lightweight API tests (no training required for basic checks)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.config import ARTIFACTS

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert "artifacts" in body
    assert "api_key_required" in body
    assert isinstance(body["api_key_required"], bool)
    assert "brand" in body
    assert body.get("auth_mode") in ("anonymous", "single", "multi")


def test_v1_usage_requires_auth_when_anonymous(monkeypatch):
    monkeypatch.delenv("PLATFORM_API_KEYS", raising=False)
    monkeypatch.delenv("PLATFORM_API_KEY", raising=False)
    r = client.get("/api/v1/usage")
    assert r.status_code == 401


def test_v1_usage_metering_per_org(tmp_path, monkeypatch):
    import json as json_lib

    db = tmp_path / "meter.sqlite"
    monkeypatch.setenv("PLATFORM_USAGE_DB", str(db))
    keys = json_lib.dumps({"meter-key-a": "org_acme", "meter-key-b": "org_beta"})
    monkeypatch.setenv("PLATFORM_API_KEYS", keys)
    monkeypatch.delenv("PLATFORM_API_KEY", raising=False)

    body = {"title": "x", "body": "y " * 15, "backend": "classical"}
    ra = client.post("/api/v1/analyze", json=body, headers={"X-API-Key": "meter-key-a"})
    assert ra.status_code in (200, 503)

    ua = client.get("/api/v1/usage", headers={"X-API-Key": "meter-key-a"})
    assert ua.status_code == 200
    ja = ua.json()
    assert ja["org_id"] == "org_acme"
    assert ja["analyze_requests_total"] >= 1

    ub = client.get("/api/v1/usage", headers={"X-API-Key": "meter-key-b"})
    assert ub.status_code == 200
    jb = ub.json()
    assert jb["org_id"] == "org_beta"
    assert jb["analyze_requests_total"] == 0


def test_v1_analyze_401_when_api_key_configured(monkeypatch):
    monkeypatch.delenv("PLATFORM_API_KEYS", raising=False)
    monkeypatch.setenv("PLATFORM_API_KEY", "test-secret-for-ci")
    r = client.post(
        "/api/v1/analyze",
        json={"title": "x", "body": "y " * 15, "backend": "classical"},
    )
    assert r.status_code == 401
    r2 = client.post(
        "/api/v1/analyze",
        json={"title": "x", "body": "y " * 15, "backend": "classical"},
        headers={"X-API-Key": "test-secret-for-ci"},
    )
    assert r2.status_code in (200, 503)


def test_v1_analyze_when_model_present(monkeypatch):
    monkeypatch.delenv("PLATFORM_API_KEYS", raising=False)
    monkeypatch.delenv("PLATFORM_API_KEY", raising=False)
    if not (ARTIFACTS / "classical" / "logreg_tfidf.joblib").is_file():
        pytest.skip("Train models first: python -m src.pipeline.run_train")
    r = client.post(
        "/api/v1/analyze",
        json={
            "title": "Local team wins championship after overtime thriller",
            "body": "Fans celebrated in the downtown square as the mayor praised the players for their discipline.",
            "backend": "classical",
            "teacher_mode": False,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "platform" in data
    assert "dimensions" in data["platform"]
    assert "signal_cards" in data["platform"]
    assert 0.0 <= data["score_toward_review_0_to_1"] <= 1.0


def test_analyze_when_model_present():
    if not (ARTIFACTS / "classical" / "logreg_tfidf.joblib").is_file():
        pytest.skip("Train models first: python -m src.pipeline.run_train")
    r = client.post(
        "/api/analyze",
        json={
            "title": "Local team wins championship after overtime thriller",
            "body": "Fans celebrated in the downtown square as the mayor praised the players for their discipline.",
            "backend": "classical",
            "teacher_mode": False,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "user_summary" in data
    assert "interpretability" in data
    assert 0.0 <= data["score_toward_review_0_to_1"] <= 1.0


def test_analyze_url_blocks_private_host():
    r = client.post(
        "/api/analyze-url",
        json={"url": "http://127.0.0.1/nope", "backend": "classical"},
    )
    assert r.status_code == 400


def test_metrics_json_optional():
    p = ARTIFACTS / "metrics.json"
    if not p.is_file():
        pytest.skip("Run training to create metrics.json")
    m = json.loads(p.read_text(encoding="utf-8"))
    assert "classical" in m
    assert "train" in m["classical"]
