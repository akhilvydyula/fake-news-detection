"""Load-once predictors and plain-language helpers for the API."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
import tensorflow as tf
from sklearn.pipeline import Pipeline

from src.config import ARTIFACTS
from src.data.preprocess import combine_title_body

Backend = Literal["classical", "bilstm", "mini_transformer"]


@lru_cache(maxsize=1)
def _load_classical_pipeline() -> Pipeline | None:
    path = ARTIFACTS / "classical" / "logreg_tfidf.joblib"
    if not path.is_file():
        return None
    return joblib.load(path)


@lru_cache(maxsize=1)
def _keyword_hints() -> dict[str, Any]:
    path = ARTIFACTS / "classical" / "keyword_hints.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _keras_model(kind: str) -> tf.keras.Model | None:
    path = ARTIFACTS / f"keras_{kind}" / "model.keras"
    if not path.is_file():
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


def clear_model_cache() -> None:
    _load_classical_pipeline.cache_clear()
    _keyword_hints.cache_clear()
    _cached_keras.cache_clear()
