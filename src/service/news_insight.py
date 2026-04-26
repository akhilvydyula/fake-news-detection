"""Dense classical-only insight: risk score, keyword drivers, narrative (reuses trained TF–IDF + LR)."""

from __future__ import annotations

from typing import Any, Literal

from src.service.predictor import (
    explain_classical_for_text,
    load_metrics_json,
    predict_proba_fake,
    user_friendly_summary,
    _executive_why,
)

ConcernLevel = Literal["low", "medium", "high"]


def _accuracy_from_confusion(cm: list[Any] | None) -> float | None:
    if not cm or len(cm) != 2 or len(cm[0]) != 2:
        return None
    tn, fp = int(cm[0][0]), int(cm[0][1])
    fn, tp = int(cm[1][0]), int(cm[1][1])
    t = tn + fp + fn + tp
    if t <= 0:
        return None
    return round((tn + tp) / t, 4)


def _concern_level(p: float) -> ConcernLevel:
    if p < 0.35:
        return "low"
    if p < 0.55:
        return "medium"
    return "high"


def _split_phrases(phrases: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    toward_review = [x for x in phrases if x.get("effect") == "pushes_toward_review"]
    toward_reliable = [x for x in phrases if x.get("effect") == "pushes_toward_reliable"]
    return toward_review, toward_reliable


def _narrative_paragraph(
    p: float, summary: dict[str, str], toward_review: list[dict[str, Any]]
) -> str:
    pct = int(round(p * 100))
    bits = [
        summary["detail"],
        (
            "For public-interest triage (not legal or clinical advice): a higher score means the wording "
            "is more statistically similar to articles in our training set that were labeled as needing "
            "extra editorial care—not proof of harm or intent."
        ),
    ]
    if toward_review[:3]:
        bits.append(
            "Phrases that most increased the review signal here: "
            + ", ".join(str(x.get("phrase", "")) for x in toward_review[:5])
            + "."
        )
    return " ".join(bits)


def _holdout_from_metrics(metrics: dict[str, Any] | None) -> dict[str, Any]:
    if not metrics or "classical" not in metrics:
        return {
            "available": False,
            "note": "After you run training, hold-out metrics from metrics.json appear here (accuracy, F1, ROC-AUC).",
        }
    classical = metrics["classical"]
    test = classical.get("test") or {}
    val = classical.get("val") or {}
    acc_test = _accuracy_from_confusion(test.get("confusion_matrix"))
    acc_val = _accuracy_from_confusion(val.get("confusion_matrix"))
    return {
        "available": True,
        "classical_tfidf_logistic": {
            "holdout_test": {
                "accuracy": acc_test,
                "f1": test.get("f1"),
                "precision": test.get("precision"),
                "recall": test.get("recall"),
                "roc_auc": test.get("roc_auc"),
            },
            "holdout_validation": {
                "accuracy": acc_val,
                "f1": val.get("f1"),
                "roc_auc": val.get("roc_auc"),
            },
        },
        "note": (
            "Figures come from the last `python -m src.pipeline.run_train` run on held-out data. "
            "They describe the model, not this single article."
        ),
    }


def build_text_insight(text: str) -> dict[str, Any] | None:
    """
    Single classical inference + rich explanation. No TensorFlow.
    """
    p = predict_proba_fake(text, "classical")
    if p is None:
        return None
    phrases = explain_classical_for_text(text, top_k=18)
    summary = user_friendly_summary(p)
    toward_review, toward_reliable = _split_phrases(phrases)
    executive = _executive_why(summary, phrases)
    narrative = _narrative_paragraph(p, summary, toward_review)
    metrics = load_metrics_json()

    risk_aspects: list[str] = [
        (
            f"Model-estimated share of language patterns associated with the “needs review” class in training: "
            f"{int(round(p * 100))}% (scale 0–100; not a probability of falsehood)."
        ),
    ]
    if toward_review[:3]:
        risk_aspects.append(
            "Statistical drivers (TF–IDF terms weighted by logistic regression) that pushed toward review: "
            + ", ".join(str(x.get("phrase", "")) for x in toward_review[:8])
            + "."
        )
    if toward_reliable[:2]:
        risk_aspects.append(
            "Language cues that pulled toward the reliable-style class: "
            + ", ".join(str(x.get("phrase", "")) for x in toward_reliable[:6])
            + "."
        )

    return {
        "model": {
            "name": "classical_tfidf_logistic_regression",
            "description": "TF–IDF bag-of-words + logistic regression (same artifact as high-speed /api/v1/analyze classical path).",
            "holdout_quality": _holdout_from_metrics(metrics),
        },
        "fake_risk": {
            "score_toward_review_0_to_1": round(p, 4),
            "percent_scale_toward_review": int(round(p * 100)),
            "verdict": summary["verdict"],
            "headline": summary["headline"],
            "detail": summary["detail"],
            "simple_scale": summary["simple_scale"],
        },
        "why": {
            "executive_summary": executive,
            "longer_story": narrative,
        },
        "keywords": {
            "toward_editorial_review": toward_review,
            "toward_reliable_style": toward_reliable,
            "method": (
                "Per-text TF–IDF attribution: phrases ranked by contribution to log-odds of the review class "
                "on this deployment’s trained weights."
            ),
        },
        "societal_concern": {
            "level": _concern_level(p),
            "rationale": (
                "Coarse queue-priority label derived from the same triage score (not sentiment or toxicity detection). "
                "Use editorial judgment before any public action."
            ),
            "risk_aspects": risk_aspects,
        },
    }
