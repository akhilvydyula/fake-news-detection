"""API dependencies: optional single or multi-tenant API keys."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass(frozen=True)
class PlatformAuth:
    """Resolved caller when v1 routes require or accept API keys."""

    org_id: str | None
    """None when anonymous access is allowed (no keys configured)."""

    authenticated: bool
    """True if a valid key was supplied (or required and matched)."""


def _key_to_org_map() -> dict[str, str]:
    raw = os.environ.get("PLATFORM_API_KEYS", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in data.items():
        if k is None or v is None:
            continue
        key = str(k).strip()
        org = str(v).strip()
        if key and org:
            out[key] = org
    return out


def auth_configured() -> bool:
    """True if any mode requires clients to send X-API-Key for protected routes."""
    if os.environ.get("PLATFORM_API_KEY", "").strip():
        return True
    return bool(_key_to_org_map())


def auth_mode() -> Literal["anonymous", "single", "multi"]:
    if _key_to_org_map():
        return "multi"
    if os.environ.get("PLATFORM_API_KEY", "").strip():
        return "single"
    return "anonymous"


def resolve_platform_auth(api_key: str | None) -> PlatformAuth:
    """
    Multi-tenant: set PLATFORM_API_KEYS JSON object, e.g. {"secret-a":"org_acme","secret-b":"org_beta"}.
    Single-tenant: set PLATFORM_API_KEY and optional PLATFORM_DEFAULT_ORG_ID (default 'default').
    If neither is set, returns anonymous PlatformAuth (org_id None, authenticated False).
    """
    key_map = _key_to_org_map()
    single = os.environ.get("PLATFORM_API_KEY", "").strip()
    default_org = os.environ.get("PLATFORM_DEFAULT_ORG_ID", "default").strip() or "default"

    if key_map:
        if not api_key or not api_key.strip():
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing X-API-Key. Use a key from PLATFORM_API_KEYS.",
            )
        org = key_map.get(api_key.strip())
        if org is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid X-API-Key.",
            )
        return PlatformAuth(org_id=org, authenticated=True)

    if single:
        if not api_key or api_key.strip() != single:
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing X-API-Key. Set header to match server PLATFORM_API_KEY.",
            )
        return PlatformAuth(org_id=default_org, authenticated=True)

    return PlatformAuth(org_id=None, authenticated=False)


def require_platform_api_key(api_key: str | None = Security(_api_key_header)) -> PlatformAuth:
    """Use on routes that share the same key rules as POST /api/v1/analyze."""
    return resolve_platform_auth(api_key)
