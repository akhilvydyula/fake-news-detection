"""SQLite-backed request counts per org (for API metering)."""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.config import DATA_INTERIM

_lock = threading.Lock()


def usage_db_path() -> Path:
    raw = os.environ.get("PLATFORM_USAGE_DB", "").strip()
    if raw:
        return Path(raw)
    return DATA_INTERIM / "platform_usage.sqlite"


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS api_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            org_id TEXT NOT NULL,
            path TEXT NOT NULL,
            status_code INTEGER NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_org_ts ON api_usage (org_id, ts)")


def _connect() -> sqlite3.Connection:
    path = usage_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    _ensure_schema(conn)
    conn.commit()
    return conn


def log_usage(org_id: str, path: str, status_code: int) -> None:
    """Record one metered API call (typically POST /api/v1/analyze)."""
    if not org_id:
        return
    ts = datetime.now(timezone.utc).isoformat()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO api_usage (ts, org_id, path, status_code) VALUES (?, ?, ?, ?)",
                (ts, org_id, path, status_code),
            )
            conn.commit()
        finally:
            conn.close()


def usage_summary(org_id: str, days: int = 30) -> dict:
    """Total and per-day counts for one org within the last `days` days."""
    days = max(1, min(int(days), 366))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute(
                """
                SELECT COUNT(*) FROM api_usage
                WHERE org_id = ? AND ts >= ? AND path IN (?, ?)
                """,
                (org_id, cutoff, "/api/v1/analyze", "/api/v1/insight"),
            )
            total = int(cur.fetchone()[0])
            cur = conn.execute(
                """
                SELECT substr(ts, 1, 10) AS day, COUNT(*) AS n
                FROM api_usage
                WHERE org_id = ? AND ts >= ? AND path IN (?, ?)
                GROUP BY substr(ts, 1, 10)
                ORDER BY day
                """,
                (org_id, cutoff, "/api/v1/analyze", "/api/v1/insight"),
            )
            by_day = [{"day": row[0], "analyze_requests": row[1]} for row in cur.fetchall()]
        finally:
            conn.close()
    return {
        "org_id": org_id,
        "window_days": days,
        "analyze_requests_total": total,
        "analyze_requests_by_day": by_day,
    }
