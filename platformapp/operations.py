"""Shared request handling used by API views (mirrors previous FastAPI helpers)."""

from __future__ import annotations

import os
from typing import Any

import httpx

from src.api.deps import PlatformAPIError
from src.api.schemas import V1AnalyzeRequest
from src.ingest.fetch_url import fetch_url_text
from src.service.predictor import build_full_text


def resolve_text_and_source(req: V1AnalyzeRequest) -> tuple[str, dict[str, Any]]:
    if req.url is not None:
        try:
            body_text, meta = fetch_url_text(str(req.url))
        except ValueError as e:
            raise PlatformAPIError(400, str(e)) from e
        except httpx.HTTPError as e:
            raise PlatformAPIError(502, f"Could not fetch URL: {e}") from e
        text = build_full_text(req.title, body_text)
        src = {
            "type": "url",
            **meta,
            "compliance_note": "Process only content you have rights to use.",
        }
    else:
        text = build_full_text(req.title, req.body)
        src = {"type": "paste"}
    return text, src


def compliance_url_note() -> str:
    return "Use only where you have rights to retrieve and process this content."


def brand_name() -> str:
    return os.environ.get("PLATFORM_BRAND_NAME", "News Trust Platform")
