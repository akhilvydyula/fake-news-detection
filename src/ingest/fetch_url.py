"""
Fetch public article HTML and extract plain text for scoring.

Only use on sites you are allowed to access (terms of service, robots.txt).
This is for product-style triage, not bulk scraping of third-party news sites.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

MAX_RESPONSE_BYTES = 2_000_000
TIMEOUT_SEC = 20.0
USER_AGENT = (
    "FakeNewsTriageBot/0.1 (+https://example.com; editorial research; contact: your-email)"
)


def _hostname_blocked(host: str) -> bool:
    h = host.lower().strip("[]")
    if h in ("localhost", "0.0.0.0"):
        return True
    if h.endswith(".local") or h.endswith(".internal"):
        return True
    try:
        ip = ipaddress.ip_address(h)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True
    except ValueError:
        pass
    # Obvious private LAN patterns (hostname not resolved here)
    if re.match(
        r"^(127\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.|169\.254\.)",
        h,
    ):
        return True
    return False


def fetch_url_text(url: str) -> tuple[str, dict[str, Any]]:
    """
    GET url and return (plain_text, metadata).

    Raises ValueError for blocked hosts or bad schemes.
    Raises httpx.HTTPError on network/HTTP failures.
    """
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http and https URLs are allowed.")
    host = parsed.hostname
    if not host or _hostname_blocked(host):
        raise ValueError("URL host is not allowed (private networks / localhost blocked).")

    meta: dict[str, Any] = {"requested_url": url, "final_url": None, "bytes_read": 0}

    with httpx.Client(
        follow_redirects=True,
        timeout=TIMEOUT_SEC,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
    ) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            ctype = (resp.headers.get("content-type") or "").lower()
            meta["final_url"] = str(resp.url)
            chunks: list[bytes] = []
            total = 0
            for chunk in resp.iter_bytes():
                total += len(chunk)
                if total > MAX_RESPONSE_BYTES:
                    raise ValueError(f"Response larger than {MAX_RESPONSE_BYTES} bytes; refusing to read further.")
                chunks.append(chunk)
            raw = b"".join(chunks)
            meta["bytes_read"] = len(raw)

    if "html" not in ctype and not raw.lstrip().startswith(b"<"):
        raise ValueError("URL did not return HTML; paste the article text manually.")

    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    title_el = soup.find("title")
    title = title_el.get_text(strip=True) if title_el else ""
    # Prefer article/main if present
    main = soup.find("article") or soup.find("main") or soup.body
    if main:
        body = main.get_text(separator="\n", strip=True)
    else:
        body = soup.get_text(separator="\n", strip=True)
    text = f"{title}\n\n{body}".strip() if title else body.strip()
    if len(text) < 40:
        raise ValueError("Extracted very little text; the page may require JavaScript or login.")
    meta["extracted_chars"] = len(text)
    return text, meta
