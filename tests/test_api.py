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
                "force_async": True,
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
    assert "last_change" in job
    assert job["last_change"] == job["submitted_at"]


def test_queue_submit_small_body_sync_default_succeeds(monkeypatch):
    monkeypatch.delenv("PLATFORM_DEMO_SYNC_SMALL_JOBS", raising=False)
    monkeypatch.setenv("PLATFORM_DEMO_SYNC_MAX_CHARS", "5000")
    monkeypatch.setattr("platformapp.views.settings.DEBUG", True)

    def _fake_run(_req):
        return {
            "score_toward_review_0_to_1": 0.12,
            "platform": {"article_summary": "demo summary", "dimensions": {}, "signal_cards": []},
        }

    monkeypatch.setattr("platformapp.views.run_analysis_job", _fake_run)
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
    assert submit.status_code == 200
    payload = json.loads(submit.content.decode("utf-8"))
    assert payload["status"] == "succeeded"
    assert payload["total_ms"] >= 0
    assert payload["queue_wait_ms"] >= 0
    assert payload["processing_ms"] >= 0
    status = client.get(f"/api/v1/jobs/{payload['job_id']}")
    assert status.status_code == 200
    job = json.loads(status.content.decode("utf-8"))
    assert job["status"] == "succeeded"
    assert job["processed_at"] is not None
    assert job["last_change"] == job["processed_at"]
    assert (job.get("result") or {}).get("summary") == "demo summary"
    assert job["total_ms"] >= 0
    assert job["queue_wait_ms"] >= 0
    assert job["processing_ms"] >= 0


def test_queue_submit_force_async_creates_pending(monkeypatch):
    monkeypatch.setenv("PLATFORM_DEMO_SYNC_SMALL_JOBS", "1")
    monkeypatch.setenv("PLATFORM_DEMO_SYNC_MAX_CHARS", "5000")

    submit = client.post(
        "/api/v1/jobs/submit",
        data=json.dumps(
            {
                "org_id": "demo-org",
                "title": "Queue sample title",
                "body": "Queue sample body that has enough words to pass validation in worker logic.",
                "backend": "classical",
                "force_async": True,
            }
        ),
        content_type="application/json",
    )
    assert submit.status_code == 202
    payload = json.loads(submit.content.decode("utf-8"))
    assert payload["status"] == "pending"


def test_queue_run_now_turns_pending_to_succeeded(monkeypatch):
    monkeypatch.setenv("PLATFORM_DEMO_SYNC_SMALL_JOBS", "1")
    monkeypatch.setenv("PLATFORM_DEMO_SYNC_MAX_CHARS", "5000")

    def _fake_run(_req):
        return {
            "score_toward_review_0_to_1": 0.42,
            "platform": {"article_summary": "run-now summary", "dimensions": {}, "signal_cards": []},
        }

    monkeypatch.setattr("platformapp.views.run_analysis_job", _fake_run)
    submit = client.post(
        "/api/v1/jobs/submit",
        data=json.dumps(
            {
                "org_id": "demo-org",
                "title": "Queue sample title",
                "body": "Queue sample body that has enough words to pass validation in worker logic.",
                "backend": "classical",
                "force_async": True,
            }
        ),
        content_type="application/json",
    )
    payload = json.loads(submit.content.decode("utf-8"))
    assert payload["status"] == "pending"
    run_now = client.post(
        f"/api/v1/jobs/{payload['job_id']}/run-now",
        data=json.dumps({"org_id": "demo-org"}),
        content_type="application/json",
    )
    assert run_now.status_code == 200
    job = json.loads(run_now.content.decode("utf-8"))
    assert job["status"] == "succeeded"
    assert (job.get("result") or {}).get("summary") == "run-now summary"
    assert job["total_ms"] >= 0
    assert job["queue_wait_ms"] >= 0
    assert job["processing_ms"] >= 0


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


def test_v1_detect_alias_and_alert_threshold(monkeypatch):
    monkeypatch.delenv("PLATFORM_API_KEYS", raising=False)
    monkeypatch.delenv("PLATFORM_API_KEY", raising=False)
    monkeypatch.setenv("PLATFORM_ALERT_THRESHOLD", "0.7")

    def _fake_base_response(_text, _backend, _teacher):
        return {
            "score_toward_review_0_to_1": 0.91,
            "platform": {
                "article_summary": "summary",
                "dimensions": {"composite_attention_0_to_1": 0.88},
                "signal_cards": [],
            },
        }

    monkeypatch.setattr("platformapp.views.build_api_response", _fake_base_response)
    monkeypatch.setattr("platformapp.views.enrich_platform_payload", lambda base, _text, _backend: base)
    r = client.post(
        "/api/v1/detect",
        data=json.dumps(
            {
                "title": "Alert threshold example",
                "body": "This body is long enough to pass validation and trigger fake scorer output.",
                "org_id": "org-alert",
            }
        ),
        content_type="application/json",
    )
    assert r.status_code == 200
    body = json.loads(r.content.decode("utf-8"))
    assert body["alert_recommended"] is True
    assert "alert_reason" in body
    assert body["tenant"]["org_id"] == "org-alert"


def test_cases_crud_state_transition_and_events():
    create = client.post(
        "/api/v1/cases",
        data=json.dumps(
            {
                "org_id": "org-cases",
                "title": "Case one",
                "article_text": "Body text for case one with enough context for tracking.",
                "severity": 0.82,
                "assignee": "alice",
            }
        ),
        content_type="application/json",
    )
    assert create.status_code == 201
    created = json.loads(create.content.decode("utf-8"))
    case_id = created["id"]
    assert created["state"] == "NEW"

    listing = client.get("/api/v1/cases?org_id=org-cases")
    assert listing.status_code == 200
    listing_body = json.loads(listing.content.decode("utf-8"))
    assert listing_body["count"] >= 1
    assert any(item["id"] == case_id for item in listing_body["cases"])

    patch = client.patch(
        f"/api/v1/cases/{case_id}",
        data=json.dumps(
            {
                "org_id": "org-cases",
                "state": "UNDER_REVIEW",
                "assignee": "bob",
            }
        ),
        content_type="application/json",
    )
    assert patch.status_code == 200
    patched = json.loads(patch.content.decode("utf-8"))
    assert patched["state"] == "UNDER_REVIEW"
    assert patched["assignee"] == "bob"
    assert len(patched["events"]) >= 2
    event_types = {evt["event_type"] for evt in patched["events"]}
    assert "case_created" in event_types
    assert "state_changed" in event_types
    assert "assignee_changed" in event_types

    detail = client.get(f"/api/v1/cases/{case_id}?org_id=org-cases")
    assert detail.status_code == 200
    detail_body = json.loads(detail.content.decode("utf-8"))
    assert detail_body["id"] == case_id
    assert isinstance(detail_body["events"], list)


def test_cases_are_org_scoped():
    c1 = client.post(
        "/api/v1/cases",
        data=json.dumps({"org_id": "org-a", "title": "A"}),
        content_type="application/json",
    )
    c2 = client.post(
        "/api/v1/cases",
        data=json.dumps({"org_id": "org-b", "title": "B"}),
        content_type="application/json",
    )
    assert c1.status_code == 201
    assert c2.status_code == 201
    case_b_id = json.loads(c2.content.decode("utf-8"))["id"]

    list_a = client.get("/api/v1/cases?org_id=org-a")
    data_a = json.loads(list_a.content.decode("utf-8"))
    assert all(item["org_id"] == "org-a" for item in data_a["cases"])
    assert all(item["id"] != case_b_id for item in data_a["cases"])

    forbidden = client.patch(
        f"/api/v1/cases/{case_b_id}",
        data=json.dumps({"org_id": "org-a", "state": "ESCALATED"}),
        content_type="application/json",
    )
    assert forbidden.status_code == 404
