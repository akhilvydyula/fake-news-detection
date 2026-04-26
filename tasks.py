"""
Cross-platform task runner (Invoke).

Teaches: same ideas as Make — named recipes, less shell drift — but pure Python and works well on Windows.

Usage (from project root, after `pip install invoke` or `pip install -e ".[dev]"`):
  invoke --list
  invoke install
  invoke venv
  invoke train
  invoke train-quick
  invoke serve
  invoke test
  invoke doctor     # artifact + UI paths (no TF)
  invoke lab        # quick train + serve (smoke)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from invoke import task

ROOT = Path(__file__).resolve().parent


def _py() -> str:
    return sys.executable


@task(
    help={
        "dev": "Include pytest + invoke (same as pip install -e \".[dev]\")",
    }
)
def install(c, dev=False):
    """Install dependencies (editable project optional)."""
    extras = ".[dev]" if dev else "."
    c.run(f"{_py()} -m pip install -U pip", cwd=str(ROOT))
    c.run(f"{_py()} -m pip install -e {extras}", cwd=str(ROOT))


@task(help={"dev": "Also install dev dependencies into the new venv"})
def venv(c, dev=False):
    """Create .venv with the standard library venv module."""
    vdir = ROOT / ".venv"
    c.run(f'{_py()} -m venv "{vdir}"', cwd=str(ROOT))
    py = vdir / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
    extras = ".[dev]" if dev else "."
    c.run(f'"{py}" -m pip install -U pip', cwd=str(ROOT))
    c.run(f'"{py}" -m pip install -e {extras}', cwd=str(ROOT))
    print("\nNext: activate the environment, then `invoke train` or `invoke serve`:")
    if os.name == "nt":
        print(r"  .\.venv\Scripts\Activate.ps1")
    else:
        print("  source .venv/bin/activate")


@task(
    help={
        "quick": "Smaller sample + 1 Keras epoch (smoke test)",
        "skip_build": "Reuse CSVs in data/processed/",
        "mlflow": "Log run to MLflow (./mlruns by default)",
    }
)
def train(c, quick=False, skip_build=False, mlflow=False):
    """Build data (unless skipped) and train all models."""
    parts = [_py(), "-m", "src.pipeline.run_train"]
    if quick:
        parts.append("--quick")
    if skip_build:
        parts.append("--skip-build")
    if mlflow:
        parts.append("--mlflow")
    c.run(" ".join(parts), cwd=str(ROOT))


@task
def train_quick(c):
    """Quick training on existing CSVs (smoke test)."""
    parts = [_py(), "-m", "src.pipeline.run_train", "--quick", "--skip-build"]
    c.run(" ".join(parts), cwd=str(ROOT))


@task(
    help={
        "host": "Bind address",
        "port": "Port",
    }
)
def serve(c, host="127.0.0.1", port=8000):
    """Run Django (dashboard + JSON APIs) with the dev autoreload server."""
    c.run(
        f'{_py()} manage.py runserver {host}:{port}',
        cwd=str(ROOT),
    )


@task
def test(c):
    """Run pytest."""
    c.run(f"{_py()} -m pytest -q", cwd=str(ROOT))


@task
def doctor(c):
    """Check artifact files and UI paths (no TensorFlow import). Exit 1 if classical model missing."""
    c.run(f'{_py()} -m src.pipeline.doctor', cwd=str(ROOT))


@task
def mlflow_ui(c, uri=""):
    """Start MLflow UI (default ./mlruns)."""
    u = uri or os.environ.get("MLFLOW_TRACKING_URI", str(ROOT / "mlruns"))
    c.run(f'{_py()} -m mlflow ui --backend-store-uri "{u}"', cwd=str(ROOT))


@task
def lab(c):
    """Smoke workflow: quick train on existing CSVs, then dev server (blocks)."""
    train_quick(c)
    serve(c)
