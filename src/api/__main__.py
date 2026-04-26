"""Run the News Trust Platform API + dashboard: `python -m src.api` (after `pip install -e .`)."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.environ.get("NTP_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.environ.get("NTP_PORT", "8000"))
    reload = os.environ.get("NTP_RELOAD", "1").lower() not in ("0", "false", "no", "off")
    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    main()
