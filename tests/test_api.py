"""Lightweight API tests (no training required for basic checks)."""

from __future__ import annotations

import json

import pytest
from django.test import Client
from django.utils import timezone

from src.config import ARTIFACTS
from platformapp.models import AnalysisJob, WorkerHeartbeat

pytestmark = pytest.mark.django_db

client = Client()


def test_platform_assets_served():
    r = client.get("/assets/platform.js")
    assert r.status_code == 200
    assert "application/javascript" in (r.headers.get("content-type") or "")
    r2 = client.get("/assets/platform.css")
    assert r2.status_code == 200


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = json.loads(r.content.decode("utf-8"))
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
    ra = client.post(
        "/api/v1/analyze",
        data=json_lib.dumps(body),
        content_type="application/json",
        headers={"X-API-Key": "meter-key-a"},
    )
    assert ra.status_code in (200, 503)

    ua = client.get("/api/v1/usage", headers={"X-API-Key": "meter-key-a"})
    assert ua.status_code == 200
    ja = json.loads(ua.content.decode("utf-8"))
    assert ja["org_id"] == "org_acme"
    assert ja["analyze_requests_total"] >= 1

    ub = client.get("/api/v1/usage", headers={"X-API-Key": "meter-key-b"})
    assert ub.status_code == 200
    jb = json.loads(ub.content.decode("utf-8"))
    assert jb["org_id"] == "org_beta"
    assert jb["analyze_requests_total"] == 0


def test_v1_analyze_401_when_api_key_configured(monkeypatch):
    monkeypatch.delenv("PLATFORM_API_KEYS", raising=False)
    monkeypatch.setenv("PLATFORM_API_KEY", "test-secret-for-ci")
    r = client.post(
        "/api/v1/analyze",
        data=json.dumps(
            {"title": "x", "body": "y " * 15, "backend": "classical"},
        ),
        content_type="application/json",
    )
    assert r.status_code == 401
    r2 = client.post(
        "/api/v1/analyze",
        data=json.dumps(
            {"title": "x", "body": "y " * 15, "backend": "classical"},
        ),
        content_type="application/json",
        headers={"X-API-Key": "test-secret-for-ci"},
    )
    assert r2.status_code in (200, 503)


def test_v1_insight_when_model_present(monkeypatch):
    monkeypatch.delenv("PLATFORM_API_KEYS", raising=False)
    monkeypatch.delenv("PLATFORM_API_KEY", raising=False)
    if not (ARTIFACTS / "classical" / "logreg_tfidf.joblib").is_file():
        pytest.skip("Train models first: python -m src.pipeline.run_train")
    r = client.post(
        "/api/v1/insight",
        data=json.dumps(
            {
                "title": "Council vote",
                "body": "Residents and officials debated funding for the transit corridor through downtown and nearby wards for over an hour.",
            },
        ),
        content_type="application/json",
    )
    assert r.status_code == 200
    data = json.loads(r.content.decode("utf-8"))
    assert "fake_risk" in data
    assert "keywords" in data
    assert "why" in data
    assert "societal_concern" in data
    assert 0.0 <= data["fake_risk"]["score_toward_review_0_to_1"] <= 1.0
    assert isinstance(data["keywords"].get("toward_editorial_review"), list)


def test_v1_analyze_when_model_present(monkeypatch):
    monkeypatch.delenv("PLATFORM_API_KEYS", raising=False)
    monkeypatch.delenv("PLATFORM_API_KEY", raising=False)
    if not (ARTIFACTS / "classical" / "logreg_tfidf.joblib").is_file():
        pytest.skip("Train models first: python -m src.pipeline.run_train")
    r = client.post(
        "/api/v1/analyze",
        data=json.dumps(
            {
                "title": "Local team wins championship after overtime thriller",
                "body": "Fans celebrated in the downtown square as the mayor praised the players for their discipline.",
                "backend": "classical",
                "teacher_mode": False,
            },
        ),
        content_type="application/json",
    )
    assert r.status_code == 200
    data = json.loads(r.content.decode("utf-8"))
    assert "platform" in data
    assert "dimensions" in data["platform"]
    assert "signal_cards" in data["platform"]
    assert 0.0 <= data["score_toward_review_0_to_1"] <= 1.0


def test_analyze_when_model_present():
    if not (ARTIFACTS / "classical" / "logreg_tfidf.joblib").is_file():
        pytest.skip("Train models first: python -m src.pipeline.run_train")
    r = client.post(
        "/api/analyze",
        data=json.dumps(
            {
                "title": "Local team wins championship after overtime thriller",
                "body": "Fans celebrated in the downtown square as the mayor praised the players for their discipline.",
                "backend": "classical",
                "teacher_mode": False,
            },
        ),
        content_type="application/json",
    )
    assert r.status_code == 200
    data = json.loads(r.content.decode("utf-8"))
    assert "user_summary" in data
    assert "interpretability" in data
    assert 0.0 <= data["score_toward_review_0_to_1"] <= 1.0


def test_analyze_url_blocks_private_host():
    r = client.post(
        "/api/analyze-url",
        data=json.dumps({"url": "http://127.0.0.1/nope", "backend": "classical"}),
        content_type="application/json",
    )
    assert r.status_code == 400


def test_metrics_json_optional():
    p = ARTIFACTS / "metrics.json"
    if not p.is_file():
        pytest.skip("Run training to create metrics.json")
    m = json.loads(p.read_text(encoding="utf-8"))
    assert "classical" in m
    assert "train" in m["classical"]


def test_queue_submit_and_status():
    submit = client.post(
        "/api/v1/jobs/submit",
        data=json.dumps(
            {
                "org_id": "demo-org",
                "title": "Queue sample title",
                "body": "Queue sample body that has enough words to pass validation in worker logic.",
                "backend": "classical",
            }
        ),
        content_type="application/json",
    )
    assert submit.status_code == 202
    payload = json.loads(submit.content.decode("utf-8"))
    assert payload["status"] == "pending"
    job_id = payload["job_id"]

    status = client.get(f"/api/v1/jobs/{job_id}")
    assert status.status_code == 200
    job = json.loads(status.content.decode("utf-8"))
    assert job["job_id"] == job_id
    assert job["org_id"] == "demo-org"
    assert job["status"] == "pending"


def test_health_includes_queue_and_worker():
    AnalysisJob.objects.create(
        org_id="health-org",
        title="t",
        body="Body with enough characters for queue health check.",
        status=AnalysisJob.Status.PENDING,
    )
    WorkerHeartbeat.objects.update_or_create(
        worker_name="test-worker",
        defaults={"last_seen_at": timezone.now()},
    )
    r = client.get("/api/health")
    assert r.status_code == 200
    body = json.loads(r.content.decode("utf-8"))
    assert "queue" in body
    assert body["queue"]["backlog"] >= 1
