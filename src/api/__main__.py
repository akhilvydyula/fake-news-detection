"""Run the News Trust Platform: `python -m src.api` (uses Django runserver, same as `python manage.py runserver`)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "newstrust.settings")


def main() -> None:
    if os.getcwd() != str(_ROOT):
        os.chdir(_ROOT)
    from django.core.management import execute_from_command_line

    host = os.environ.get("NTP_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = os.environ.get("NTP_PORT", "8000").strip() or "8000"
    bind = f"{host}:{port}"
    # Match prior behavior: NTP_RELOAD=0 can disable autoreload (Django: --noreload)
    noreload = os.environ.get("NTP_RELOAD", "1").lower() in ("0", "false", "no", "off")
    args = [str(_ROOT / "manage.py"), "runserver", bind]
    if noreload:
        args.append("--noreload")
    sys.argv = args
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
