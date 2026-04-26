#!/usr/bin/env python3
"""Verify POST /api/v1/analyze with the same JSON shape as the dashboard.

Usage (no server — uses Django test client, no port):
  python scripts/smoke_analyze.py

Usage (live server — same as browser fetch):
  python scripts/smoke_analyze.py --base-url http://127.0.0.1:8000

With API key (when PLATFORM_API_KEY or PLATFORM_API_KEYS is set on the server):
  python scripts/smoke_analyze.py --base-url http://127.0.0.1:8000 --api-key YOUR_KEY

Exit code 0 only if status is 200 and `platform` is present.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


# Same shape as web dashboard (paste mode). Body must be ~20+ chars after merge with title.
SAMPLE = {
    "title": "City sample: council approves transit plan after debate",
    "body": (
        "Residents filled the chamber as officials voted in favor of the downtown connector. "
        "The mayor said work could start next year if federal funds arrive. "
        "Critics asked for stronger parking and accessibility measures near stations."
    ),
    "backend": "classical",
    "teacher_mode": False,
}


def run_testclient() -> int:
    import os

    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "newstrust.settings")
    django.setup()
    from django.test import Client

    client = Client()
    r = client.post(
        "/api/v1/analyze",
        data=json.dumps(SAMPLE),
        content_type="application/json",
    )
    return _check_response(r.status_code, r.content.decode("utf-8", errors="replace"))


def run_http(base_url: str, api_key: str | None) -> int:
    base = base_url.rstrip("/")
    payload = json.dumps(SAMPLE).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    req = urllib.request.Request(
        f"{base}/api/v1/analyze",
        data=payload,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return _check_response(resp.status, body)
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", errors="replace") if e.fp else ""
        print(f"HTTP {e.code}", file=sys.stderr)
        print(text[:2000], file=sys.stderr)
        return 1


def _check_response(status: int, text: str) -> int:
    if status != 200:
        print(f"Expected 200, got {status}", file=sys.stderr)
        print(text[:2000], file=sys.stderr)
        return 1
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        print("Response is not JSON", file=sys.stderr)
        print(text[:2000], file=sys.stderr)
        return 1
    plat = data.get("platform")
    if not isinstance(plat, dict):
        print("Missing platform object", file=sys.stderr)
        return 1
    score = data.get("score_toward_review_0_to_1")
    dims = plat.get("dimensions") or {}
    n_cards = len(plat.get("signal_cards") or [])
    print("smoke_analyze: OK")
    print(f"  score_toward_review_0_to_1: {score}")
    print(f"  dimensions: {list(dims.keys())}")
    print(f"  signal_cards: {n_cards}")
    summ = plat.get("article_summary") or ""
    print(f"  article_summary chars: {len(summ)}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--base-url",
        help="If set, POST to this origin (e.g. http://127.0.0.1:8000). Otherwise use TestClient.",
    )
    p.add_argument("--api-key", default="", help="Optional X-API-Key header for live requests.")
    args = p.parse_args()
    if args.base_url:
        return run_http(args.base_url, args.api_key.strip() or None)
    return run_testclient()


if __name__ == "__main__":
    raise SystemExit(main())
