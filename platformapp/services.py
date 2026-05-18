"""RSS ingestion and model scoring services for Django.

This module is intentionally framework-light: the management command, scheduled
jobs, and future dashboards can all call the same functions.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone as dt_timezone
from email.utils import parsedate_to_datetime
from typing import Any, Literal

from django.db import transaction
from django.utils import timezone
from bs4 import BeautifulSoup

from src.service.enrichment import enrich_platform_payload
from src.service.predictor import Backend, build_api_response, build_full_text

from .models import RSSFeed, ScoredArticle

Prediction = Literal[
    "likely_reliable",
    "uncertain",
    "review_recommended",
    "model_unavailable",
    "failed",
]


def score_article(
    text: str,
    *,
    backend: Backend = "classical",
    review_threshold: float = 0.8,
) -> dict[str, Any]:
    """Score text with the existing model and return UI/API-ready fields."""
    if len(text.strip()) < 20:
        raise ValueError("Article text is too short after RSS extraction.")

    base = build_api_response(text, backend, teacher_mode=False)
    if base is None:
        return {
            "prediction": ScoredArticle.Prediction.MODEL_UNAVAILABLE,
            "confidence": 0.0,
            "flagged_for_review": False,
            "result_json": None,
            "error": f"Model files for backend '{backend}' are missing.",
        }

    result = enrich_platform_payload(base, text, backend)
    score = float(result.get("score_toward_review_0_to_1") or 0.0)
    verdict = result.get("user_summary", {}).get("verdict") or _prediction_from_score(score)
    return {
        "prediction": verdict,
        "confidence": round(score, 4),
        "flagged_for_review": score >= review_threshold,
        "result_json": result,
        "error": "",
    }


def fetch_and_score_feeds(
    *,
    backend: Backend = "classical",
    max_entries_per_feed: int = 25,
    review_threshold: float = 0.8,
) -> dict[str, int]:
    """Fetch active RSS feeds, store unseen articles, and score them."""
    try:
        import feedparser
    except ImportError as exc:  # pragma: no cover - dependency/runtime guard.
        raise RuntimeError("Install feedparser first: pip install -e \".[dev]\"") from exc

    counts = {
        "feeds_seen": 0,
        "feeds_failed": 0,
        "articles_seen": 0,
        "articles_added": 0,
        "articles_scored": 0,
        "articles_flagged": 0,
        "articles_skipped_existing": 0,
        "articles_failed": 0,
    }

    feeds = RSSFeed.objects.filter(is_active=True).order_by("name", "id")
    for feed in feeds:
        counts["feeds_seen"] += 1
        parsed = feedparser.parse(feed.url)
        if getattr(parsed, "bozo", False):
            feed.last_error = str(getattr(parsed, "bozo_exception", "RSS parse failed"))[:2000]
            feed.last_fetched_at = timezone.now()
            feed.save(update_fields=["last_error", "last_fetched_at"])
            counts["feeds_failed"] += 1
            continue

        feed.last_error = ""
        feed.last_fetched_at = timezone.now()
        feed.save(update_fields=["last_error", "last_fetched_at"])

        for entry in list(parsed.entries)[: max(1, max_entries_per_feed)]:
            counts["articles_seen"] += 1
            source_id = _entry_source_id(entry)
            if ScoredArticle.objects.filter(feed=feed, source_id=source_id).exists():
                counts["articles_skipped_existing"] += 1
                continue

            title = _entry_value(entry, "title")[:500]
            url = (_entry_value(entry, "link") or feed.url)[:1000]
            summary = _entry_value(entry, "summary")
            content = _entry_content(entry)
            article_text = build_full_text(title, content or summary)

            with transaction.atomic():
                article = ScoredArticle.objects.create(
                    feed=feed,
                    org_id=feed.org_id,
                    source_id=source_id,
                    url=url,
                    title=title,
                    summary=summary,
                    content=content or summary,
                    published_at=_entry_published_at(entry),
                    backend=backend,
                )
                counts["articles_added"] += 1

                try:
                    scored = score_article(
                        article_text,
                        backend=backend,
                        review_threshold=review_threshold,
                    )
                    article.prediction = scored["prediction"]
                    article.confidence = scored["confidence"]
                    article.flagged_for_review = scored["flagged_for_review"]
                    article.result_json = scored["result_json"]
                    article.error = scored["error"]
                    article.scored_at = timezone.now()
                    article.save(
                        update_fields=[
                            "prediction",
                            "confidence",
                            "flagged_for_review",
                            "result_json",
                            "error",
                            "scored_at",
                        ],
                    )
                    counts["articles_scored"] += 1
                    if article.flagged_for_review:
                        counts["articles_flagged"] += 1
                except Exception as exc:  # Keep one bad item from blocking the feed.
                    article.prediction = ScoredArticle.Prediction.FAILED
                    article.error = str(exc)[:4000]
                    article.scored_at = timezone.now()
                    article.save(update_fields=["prediction", "error", "scored_at"])
                    counts["articles_failed"] += 1

    return counts


def _prediction_from_score(score: float) -> Prediction:
    if score < 0.35:
        return ScoredArticle.Prediction.LIKELY_RELIABLE
    if score < 0.5:
        return ScoredArticle.Prediction.UNCERTAIN
    return ScoredArticle.Prediction.REVIEW_RECOMMENDED


def _entry_value(entry: Any, key: str) -> str:
    value = getattr(entry, key, "") or ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _entry_content(entry: Any) -> str:
    content = getattr(entry, "content", None)
    if content:
        parts: list[str] = []
        for item in content:
            value = item.get("value") if isinstance(item, dict) else getattr(item, "value", "")
            if value:
                parts.append(_plain_text(str(value)))
        if parts:
            return "\n\n".join(parts)
    return _plain_text(_entry_value(entry, "summary"))


def _plain_text(raw: str) -> str:
    if "<" not in raw or ">" not in raw:
        return raw.strip()
    soup = BeautifulSoup(raw, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def _entry_source_id(entry: Any) -> str:
    raw = (
        _entry_value(entry, "id")
        or _entry_value(entry, "guid")
        or _entry_value(entry, "link")
        or f"{_entry_value(entry, 'title')}|{_entry_value(entry, 'published')}"
    )
    if len(raw) <= 680:
        return raw
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def _entry_published_at(entry: Any) -> datetime | None:
    for key in ("published", "updated", "created"):
        raw = _entry_value(entry, key)
        if not raw:
            continue
        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            continue
        if parsed.tzinfo is None:
            return timezone.make_aware(parsed, timezone=timezone.get_current_timezone())
        return parsed.astimezone(dt_timezone.utc)
    return None
