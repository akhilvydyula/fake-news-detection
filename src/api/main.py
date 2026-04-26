"""FastAPI app: platform UI + legacy UI + REST APIs (v1 for integrations)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, HttpUrl

from src.api.deps import (
    PlatformAuth,
    auth_configured,
    auth_mode,
    require_platform_api_key,
)
from src.api.usage_store import log_usage, usage_summary
from src.config import PROJECT_ROOT
from src.ingest.fetch_url import fetch_url_text
from src.service.enrichment import enrich_platform_payload
from src.service.predictor import (
    artifacts_ready,
    build_api_response,
    build_full_text,
    load_metrics_json,
    product_framing,
    _keyword_hints,
)

STATIC_DIR = PROJECT_ROOT / "static"
WEB_DIR = PROJECT_ROOT / "web"

app = FastAPI(
    title="News Trust Platform API",
    description="Detector management & triage API for newsrooms. v1 for secure integrations.",
    version="0.5.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    title: str = Field(default="", max_length=500)
    body: str = Field(default="", max_length=50_000)
    backend: Literal["classical", "bilstm", "mini_transformer"] = "classical"
    teacher_mode: bool = Field(
        default=False,
        description="If true, include precision/recall from last training run when available.",
    )


class AnalyzeUrlRequest(BaseModel):
    url: HttpUrl
    backend: Literal["classical", "bilstm", "mini_transformer"] = "classical"
    teacher_mode: bool = False


class V1AnalyzeRequest(BaseModel):
    """Unified payload for dashboard and partner integrations."""

    title: str = Field(default="", max_length=500)
    body: str = Field(default="", max_length=55_000)
    url: HttpUrl | None = None
    backend: Literal["classical", "bilstm", "mini_transformer"] = "classical"
    teacher_mode: bool = False


@app.get("/api/health")
def health() -> dict[str, Any]:
    ready = artifacts_ready()
    return {
        "status": "ok" if any(ready.values()) else "no_models",
        "artifacts": ready,
        "api_key_required": auth_configured(),
        "auth_mode": auth_mode(),
        "brand": os.environ.get("PLATFORM_BRAND_NAME", "News Trust Platform"),
        "usage_endpoint": "/api/v1/usage",
    }


@app.get("/api/model-info")
def model_info(teacher_mode: bool = False) -> dict[str, Any]:
    metrics = load_metrics_json()
    hints = _keyword_hints()
    base: dict[str, Any] = {
        "what_this_does": (
            "This tool compares your draft to patterns in a research dataset. "
            "It does not verify facts, names, or dates. Always use normal journalism checks."
        ),
        "product_framing": product_framing(),
        "artifacts": artifacts_ready(),
        "v1_endpoint": "/api/v1/analyze",
    }
    if teacher_mode and metrics:
        base["training_metrics"] = metrics
        base["overfitting_note"] = metrics.get("overfitting_note")
    if teacher_mode and hints:
        base["global_keyword_hints"] = {
            "note": hints.get("note"),
            "examples_pushed_toward_review_in_training": hints.get("ngrams_associated_with_predicted_fake", [])[:15],
        }
    return base


def _resolve_text_and_source(req: V1AnalyzeRequest) -> tuple[str, dict[str, Any]]:
    if req.url is not None:
        try:
            body_text, meta = fetch_url_text(str(req.url))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Could not fetch URL: {e}") from e
        text = build_full_text(req.title, body_text)
        src = {"type": "url", **meta, "compliance_note": "Process only content you have rights to use."}
    else:
        text = build_full_text(req.title, req.body)
        src = {"type": "paste"}
    return text, src


@app.post("/api/v1/analyze")
def analyze_v1(
    req: V1AnalyzeRequest,
    auth: PlatformAuth = Depends(require_platform_api_key),
) -> dict[str, Any]:
    """
    Platform analyze: same scoring as legacy endpoints plus `platform` block
    (summary, dimensions, `signal_cards`). Optional `X-API-Key` when keys are configured.
    When authenticated, response may include `tenant.org_id` and the call is metered (see GET /api/v1/usage).
    """
    status = 200
    try:
        text, src = _resolve_text_and_source(req)
        if len(text.strip()) < 20:
            raise HTTPException(status_code=400, detail="Text too short after resolving URL or paste.")

        base = build_api_response(text, req.backend, req.teacher_mode)
        if base is None:
            raise HTTPException(
                status_code=503,
                detail="Model files are missing. Run: python -m src.pipeline.run_train",
            )
        out = enrich_platform_payload(base, text, req.backend)
        out["source"] = src
        out["platform"]["brand_hint"] = os.environ.get("PLATFORM_BRAND_NAME", "News Trust Platform")
        if auth.org_id is not None:
            out["tenant"] = {"org_id": auth.org_id}
        return out
    except HTTPException as e:
        status = e.status_code
        raise
    finally:
        if auth.org_id is not None:
            log_usage(auth.org_id, "/api/v1/analyze", status)


@app.get("/api/v1/usage")
def usage_v1(
    days: int = 30,
    auth: PlatformAuth = Depends(require_platform_api_key),
) -> dict[str, Any]:
    """
    Per-organization analyze call counts (POST /api/v1/analyze only). Requires the same auth as analyze.
    In anonymous demo mode (no keys configured), returns 401.
    """
    if auth.org_id is None:
        raise HTTPException(
            status_code=401,
            detail="Usage reporting requires API keys. Set PLATFORM_API_KEY or PLATFORM_API_KEYS on the server.",
        )
    return usage_summary(auth.org_id, days=min(max(days, 1), 366))


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest) -> dict[str, Any]:
    text = build_full_text(req.title, req.body)
    if len(text.strip()) < 20:
        raise HTTPException(
            status_code=400,
            detail="Please enter a longer headline or article snippet (at least ~20 characters).",
        )

    out = build_api_response(text, req.backend, req.teacher_mode)
    if out is None:
        raise HTTPException(
            status_code=503,
            detail="Model files are missing. Run: python -m src.pipeline.run_train",
        )
    out["source"] = {"type": "paste"}
    return out


@app.post("/api/analyze-url")
def analyze_url(req: AnalyzeUrlRequest) -> dict[str, Any]:
    try:
        text, meta = fetch_url_text(str(req.url))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch URL: {e}") from e

    if len(text.strip()) < 20:
        raise HTTPException(status_code=400, detail="Extracted text too short.")

    out = build_api_response(text, req.backend, req.teacher_mode)
    if out is None:
        raise HTTPException(
            status_code=503,
            detail="Model files are missing. Run: python -m src.pipeline.run_train",
        )
    out["source"] = {
        "type": "url",
        **meta,
        "compliance_note": "Use only where you have rights to retrieve and process this content.",
    }
    return out


@app.get("/")
def platform_index() -> FileResponse:
    index_path = WEB_DIR / "index.html"
    if not index_path.is_file():
        index_path = STATIC_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail="web/index.html missing")
    return FileResponse(index_path)


@app.get("/classic")
def classic_index() -> FileResponse:
    p = STATIC_DIR / "index.html"
    if not p.is_file():
        raise HTTPException(status_code=404, detail="legacy UI missing")
    return FileResponse(p)


if (WEB_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(WEB_DIR / "assets")), name="platform-assets")

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
