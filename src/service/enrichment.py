"""Platform enrichment: extractive summary, AI-style heuristics, dashboard signal cards (not autonomous agents)."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Literal

from src.service.predictor import Backend

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def extractive_summary(text: str, max_sentences: int = 4, max_chars: int = 720) -> str:
    """Simple lead-style summary (no LLM)."""
    text = text.strip()
    if not text:
        return ""
    parts = [p.strip() for p in _SENT_SPLIT.split(text) if len(p.strip()) > 15]
    out: list[str] = []
    for p in parts[:max_sentences]:
        out.append(p)
        if len(" ".join(out)) >= max_chars:
            break
    s = " ".join(out)
    if len(s) > max_chars:
        s = s[: max_chars - 1].rsplit(" ", 1)[0] + "…"
    return s


def heuristic_ai_style_signals(text: str) -> dict[str, Any]:
    """
    Experimental signals sometimes correlated with templated or assistant-like prose.
    Not a forensic AI detector — disclose in API and UI.
    """
    t = text.lower()
    reasons: list[str] = []
    score = 0.0
    boilerplate = [
        "as an ai",
        "as a language model",
        "i cannot browse",
        "i don't have access to",
        "i don't have real-time",
        "i'm an ai",
        "chatgpt",
        "large language model",
    ]
    for b in boilerplate:
        if b in t:
            score += 0.2
            reasons.append(f"Phrase often associated with assistant output: “{b}”.")
    words = re.findall(r"[a-zA-Z']+", text.lower())
    if len(words) > 80:
        ttr = len(set(words)) / len(words)
        if ttr < 0.28:
            score += 0.18
            reasons.append("Low lexical variety for this length (weak signal; wire copy can look similar).")
    if len(words) > 40:
        bigrams = [tuple(words[i : i + 2]) for i in range(len(words) - 1)]
        if bigrams:
            top = Counter(bigrams).most_common(1)[0][1]
            if top > max(5, len(bigrams) * 0.11):
                score += 0.12
                reasons.append("Repeated phrasing clusters detected (may be templated or duplicated blocks).")
    score = round(min(1.0, score), 4)
    return {
        "score_0_to_1": score,
        "method": "rule_and_lexical_heuristic",
        "reasons": reasons[:8],
        "disclaimer": (
            "Experimental only. Does not prove human vs machine authorship; use dedicated detectors and editorial policy."
        ),
    }


def _status_from_score(x: float, low: float = 0.32, high: float = 0.55) -> Literal["low", "medium", "elevated"]:
    if x < low:
        return "low"
    if x < high:
        return "medium"
    return "elevated"


def enrich_platform_payload(
    base: dict[str, Any],
    text: str,
    backend: Backend,
) -> dict[str, Any]:
    """Add dashboard fields: summary, dimensions, signal_cards for the UI and API."""
    p = float(base["score_toward_review_0_to_1"])
    ai = heuristic_ai_style_signals(text)
    ai_s = float(ai["score_0_to_1"])
    composite = round(min(1.0, 0.62 * p + 0.38 * ai_s), 4)
    summary = extractive_summary(text)
    verdict = base["user_summary"]["verdict"]

    signal_cards: list[dict[str, Any]] = [
        {
            "id": "credibility_pattern",
            "title": "Misinformation-style (ML)",
            "icon": "◎",
            "score_0_to_1": p,
            "attention": _status_from_score(p),
            "one_liner": "Score vs. training labels (misleading-style vs reliable-style). Not a fact check.",
        },
        {
            "id": "ai_style_heuristic",
            "title": "AI-style patterns (heuristic)",
            "icon": "✦",
            "score_0_to_1": ai_s,
            "attention": _status_from_score(ai_s, 0.25, 0.45),
            "one_liner": "Rule-based cues (phrases, repetition, variety). Experimental; not proof of authorship.",
            "signals": ai["reasons"],
        },
        {
            "id": "composite_triage",
            "title": "Combined triage score",
            "icon": "⬢",
            "score_0_to_1": composite,
            "attention": _status_from_score(composite),
            "one_liner": "Weighted blend for queues—adjust weights in code for your workflow.",
        },
    ]

    platform: dict[str, Any] = {
        "schema_version": "1.1",
        "brand_hint": "Configure PLATFORM_BRAND_NAME for your deployment (e.g. Valuation AI).",
        "article_summary": summary,
        "dimensions": {
            "misinformation_style_0_to_1": p,
            "ai_text_experimental_0_to_1": ai_s,
            "composite_attention_0_to_1": composite,
        },
        "verdict_short": verdict,
        "signal_cards": signal_cards,
        "ai_style_block": ai,
        "integration": {
            "analyze": "POST /api/v1/analyze",
            "usage": "GET /api/v1/usage?days=30",
            "auth": (
                "Header X-API-Key when PLATFORM_API_KEY or PLATFORM_API_KEYS is set; "
                "JSON map keys → org_id for multi-tenant metering."
            ),
        },
    }
    merged = {**base, "platform": platform}
    return merged
