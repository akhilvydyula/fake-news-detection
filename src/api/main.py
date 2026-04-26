"""FastAPI app: beginner-friendly JSON + static UI for news draft review."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, HttpUrl

from src.config import PROJECT_ROOT
from src.ingest.fetch_url import fetch_url_text
from src.service.predictor import (
    artifacts_ready,
    build_api_response,
    build_full_text,
    load_metrics_json,
    product_framing,
    _keyword_hints,
)

STATIC_DIR = PROJECT_ROOT / "static"

app = FastAPI(
    title="News draft helper",
    description="Decision support for editors—not a fact checker. Plain language for readers; optional teacher metrics.",
    version="0.3.0",
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


@app.get("/api/health")
def health() -> dict[str, Any]:
    ready = artifacts_ready()
    return {"status": "ok" if any(ready.values()) else "no_models", "artifacts": ready}


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
    """
    Fetch a public HTML page and score extracted text. Respect site ToS and robots rules;
    for production, prefer your CMS webhook or licensed feeds instead of hotlinking third parties.
    """
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
def index() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail="static/index.html missing")
    return FileResponse(index_path)


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
