"""Text cleaning and field assembly."""

from __future__ import annotations

import re
import unicodedata


_WS = re.compile(r"\s+")


def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\x00", " ")
    text = _WS.sub(" ", text).strip()
    return text


def combine_title_body(title: str | None, body: str | None) -> str:
    t = clean_text(title or "")
    b = clean_text(body or "")
    if t and b:
        return f"{t}. {b}"
    return t or b
