from __future__ import annotations

import logging
from typing import Any

from src.api.schemas import V1AnalyzeRequest
from src.service.enrichment import enrich_platform_payload
from src.service.news_insight import build_text_insight
from src.service.predictor import build_api_response

from .operations import resolve_text_and_source

logger = logging.getLogger("newstrust.jobs")


def run_analysis_job(req: V1AnalyzeRequest) -> dict[str, Any]:
    text, src = resolve_text_and_source(req)
    if len(text.strip()) < 20:
        raise ValueError("Text too short after resolving URL or paste.")
    base = build_api_response(text, req.backend, req.teacher_mode)
    if base is None:
        raise RuntimeError("Model files are missing. Run: python -m src.pipeline.run_train")
    out = enrich_platform_payload(base, text, req.backend)
    out["source"] = src
    return out


def run_insight_snapshot(req: V1AnalyzeRequest) -> dict[str, Any]:
    text, _ = resolve_text_and_source(req)
    if len(text.strip()) < 20:
        raise ValueError("Text too short after resolving URL or paste.")
    out = build_text_insight(text)
    if out is None:
        raise RuntimeError("Model files are missing. Run: python -m src.pipeline.run_train")
    return out
