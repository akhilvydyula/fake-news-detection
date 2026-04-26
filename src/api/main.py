"""FastAPI app: beginner-friendly JSON + static UI for news draft review."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.config import PROJECT_ROOT
from src.service.predictor import (
    artifacts_ready,
    build_full_text,
    explain_classical_for_text,
    load_metrics_json,
    predict_proba_fake,
    user_friendly_summary,
    _keyword_hints,
)

STATIC_DIR = PROJECT_ROOT / "static"

app = FastAPI(
    title="News draft helper",
    description="Decision support for editors—not a fact checker. Plain language for readers; optional teacher metrics.",
    version="0.2.0",
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
        raise HTTPException(status_code=400, detail="Please enter a longer headline or article snippet (at least ~20 characters).")

    p = predict_proba_fake(text, req.backend)
    if p is None:
        raise HTTPException(
            status_code=503,
            detail="Model files are missing. Run: python -m src.pipeline.run_train",
        )

    summary = user_friendly_summary(p)
    response: dict[str, Any] = {
        "score_toward_review_0_to_1": round(p, 4),
        "user_summary": summary,
        "interpretability": {
            "plain_explanation": (
                "We highlight words and phrases from your text that most moved the linear model toward "
                "“review” or “reliable,” based on weights learned from training data. "
                "This is not a list of lies—only statistical cues."
            ),
            "phrases_in_your_text": explain_classical_for_text(text, top_k=12)
            if req.backend == "classical"
            else [
                {
                    "phrase": "(Neural model)",
                    "effect": "use_classical_backend_for_word_level_hints",
                    "strength": 0.0,
                }
            ],
        },
    }

    if req.teacher_mode:
        metrics = load_metrics_json()
        if metrics and "classical" in metrics:
            c = metrics["classical"]
            response["teacher"] = {
                "test_set": c.get("test"),
                "validation_set": c.get("val"),
                "train_set": c.get("train"),
                "note": (
                    "Precision = of all drafts flagged “review,” how many were truly in the review class in the dataset. "
                    "Recall = of all truly questionable items in the dataset, how many we caught. "
                    "Compare train vs val AUC in training_metrics to spot overfitting."
                ),
            }
    return response


@app.get("/")
def index() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail="static/index.html missing")
    return FileResponse(index_path)


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
