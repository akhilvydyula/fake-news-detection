"""Doctor script: filesystem checks only."""

from __future__ import annotations

from src.pipeline.doctor import run


def test_doctor_returns_int():
    code = run()
    assert code in (0, 1)
