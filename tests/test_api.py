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


def test_metrics_json_optional():
    p = ARTIFACTS / "metrics.json"
    if not p.is_file():
        pytest.skip("Run training to create metrics.json")
    m = json.loads(p.read_text(encoding="utf-8"))
    assert "classical" in m
    assert "train" in m["classical"]
