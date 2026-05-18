"""Load-once predictors and plain-language helpers for the API."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
from sklearn.pipeline import Pipeline

# TensorFlow is imported only inside _keras_model(). Importing tf at module load
# adds tens of seconds to minutes on Windows and blocks classical (sklearn) inference.

from src.config import ARTIFACTS
from src.data.preprocess import combine_title_body

Backend = Literal["classical", "bilstm", "mini_transformer"]


@lru_cache(maxsize=1)
def _load_classical_pipeline() -> Pipeline | None:
    path = ARTIFACTS / "classical" / "logreg_tfidf.joblib"
    if not path.is_file():
        return None
    return joblib.load(path)


def warm_classical_cache() -> None:
    """Load the cached classical sklearn pipeline once (no TensorFlow)."""
    _load_classical_pipeline()


@lru_cache(maxsize=1)
def _keyword_hints() -> dict[str, Any]:
    path = ARTIFACTS / "classical" / "keyword_hints.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _keras_model(kind: str) -> Any:
    path = ARTIFACTS / f"keras_{kind}" / "model.keras"
    if not path.is_file():
        return None
    import os

    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    try:
        import tensorflow as tf
    except ImportError:
        return None

    return tf.keras.models.load_model(path)


@lru_cache(maxsize=3)
def _cached_keras(kind: str) -> tf.keras.Model | None:
    return _keras_model(kind)


def artifacts_ready() -> dict[str, bool]:
    return {
        "classical": (ARTIFACTS / "classical" / "logreg_tfidf.joblib").is_file(),
        "bilstm": (ARTIFACTS / "keras_bilstm" / "model.keras").is_file(),
        "mini_transformer": (ARTIFACTS / "keras_mini_transformer" / "model.keras").is_file(),
    }


def predict_proba_fake(text: str, backend: Backend = "classical") -> float | None:
    """Probability that text is fake / needs review (same convention as training: class 1 = fake)."""
    if backend == "classical":
        pipe = _load_classical_pipeline()
        if pipe is None:
            return None
        return float(pipe.predict_proba([text])[0, 1])
    model = _cached_keras("bilstm" if backend == "bilstm" else "mini_transformer")
    if model is None:
        return None
    p = model.predict(np.array([text], dtype=str), verbose=0).ravel()[0]
    return float(p)


def explain_classical_for_text(text: str, top_k: int = 12) -> list[dict[str, Any]]:
    """Top TF–IDF terms weighted by logistic coefficients for this specific article."""
    pipe = _load_classical_pipeline()
    if pipe is None:
        return []
    vec = pipe.named_steps["tfidf"]
    clf = pipe.named_steps["clf"]
    X = vec.transform([text])
    coef = clf.coef_.ravel()
    contrib = X.multiply(coef)
    arr = np.asarray(contrib.todense()).ravel()
    names = vec.get_feature_names_out()
    order = np.argsort(np.abs(arr))[-top_k:][::-1]
    out = []
    for i in order:
        if arr[i] == 0:
            continue
        out.append(
            {
                "phrase": str(names[i]),
                "effect": "pushes_toward_review" if arr[i] > 0 else "pushes_toward_reliable",
                "strength": round(float(abs(arr[i])), 6),
            }
        )
    return out


def user_friendly_summary(p_fake: float) -> dict[str, str]:
    """Copy for non-technical readers."""
    pct = int(round(p_fake * 100))
    if p_fake < 0.35:
        verdict = "likely_reliable"
        headline = "No strong warning signs in our automatic check"
        detail = (
            f"This draft scored {pct}% on our “needs human review” scale—on the lower end for the examples "
            "we trained on. That does not prove a story is true; it only means the wording pattern is closer "
            "to articles we labeled as reliable in our training data."
        )
    elif p_fake < 0.5:
        verdict = "uncertain"
        headline = "Mixed signals — a quick editor look is a good idea"
        detail = (
            f"The score is about {pct}%. Some phrases resemble both reliable and questionable articles from "
            "our training set. Use your normal editorial process: sources, quotes, and corroboration matter "
            "more than this number."
        )
    else:
        verdict = "review_recommended"
        headline = "Higher chance this matches questionable patterns — please review carefully"
        detail = (
            f"This draft scored {pct}% on our “needs review” scale. That often means the text shares wording "
            "or style with articles we marked as unreliable in training. It can still be true; the model "
            "does not fact-check. A human should verify claims and sources before publishing."
        )
    return {
        "verdict": verdict,
        "headline": headline,
        "detail": detail,
        "simple_scale": f"{pct}/100 toward “needs review” (not a truth score)",
    }


def build_full_text(title: str | None, body: str | None) -> str:
    return combine_title_body(title or "", body or "")


def load_metrics_json() -> dict[str, Any] | None:
    p = ARTIFACTS / "metrics.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _executive_why(summary: dict[str, str], top_phrases: list[dict[str, Any]]) -> str:
    """Short “why” blurb for UI and automation dashboards."""
    bits = [summary["headline"], summary["detail"][:280] + ("…" if len(summary["detail"]) > 280 else "")]
    if top_phrases:
        toward = [p["phrase"] for p in top_phrases[:4] if p.get("effect") == "pushes_toward_review"]
        away = [p["phrase"] for p in top_phrases[:4] if p.get("effect") == "pushes_toward_reliable"]
        if toward:
            bits.append("Phrases that nudged toward review (statistical): " + ", ".join(toward[:5]) + ".")
        if away:
            bits.append("Phrases that nudged toward reliable (statistical): " + ", ".join(away[:5]) + ".")
    return " ".join(bits)


def product_framing() -> dict[str, str]:
    """Stable copy for APIs and teaching: what automation is for."""
    return {
        "automation_role": (
            "Machine learning here automates **triage**: it ranks unseen articles so reviewers spend time "
            "on higher-risk items first. It does not replace humans for truth, law, or ethics."
        ),
        "what_models_measure": (
            "Models estimate similarity in **language patterns** to articles labeled reliable vs. needs-review "
            "in training data—not whether claims match reality. A human-written true story can score “review” "
            "if it resembles clickbait in the corpus; LLM-generated text can score “reliable” if it mimics wire style."
        ),
        "llm_generated_content": (
            "Detecting “written by AI” is a **different** problem from misinformation. You may add separate "
            "detectors or watermarking policies; this stack is trained for **misleading-style vs. mainstream-news-style** "
            "labels on a specific dataset, not universal AI authorship detection."
        ),
        "scaling_review": (
            "At high volume, use thresholds: e.g. auto-publish only below 0.3 “review” score, queue 0.3–0.5 for spot-check, "
            "require full fact-check above 0.5. Tune using your own labeled data and legal/compliance rules."
        ),
    }


def build_api_response(text: str, backend: Backend, teacher_mode: bool) -> dict[str, Any] | None:
    """Full JSON payload for /api/analyze and /api/analyze-url."""
    p = predict_proba_fake(text, backend)
    if p is None:
        return None
    summary = user_friendly_summary(p)
    phrases = (
        explain_classical_for_text(text, top_k=12)
        if backend == "classical"
        else [
            {
                "phrase": "(Use “Fast explanation” model for word-level reasons.)",
                "effect": "pushes_toward_review",
                "strength": 0.0,
            }
        ]
    )
    response: dict[str, Any] = {
        "score_toward_review_0_to_1": round(p, 4),
        "user_summary": summary,
        "interpretability": {
            "plain_explanation": (
                "We highlight words and phrases from your text that most moved the linear model toward "
                "“review” or “reliable,” based on weights learned from training data. "
                "This is not a list of lies—only statistical cues."
            ),
            "phrases_in_your_text": phrases,
        },
        "product_framing": product_framing(),
        "executive_why": _executive_why(summary, phrases if backend == "classical" else []),
    }

    if teacher_mode:
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


def clear_model_cache() -> None:
    _load_classical_pipeline.cache_clear()
    _keyword_hints.cache_clear()
    _cached_keras.cache_clear()
