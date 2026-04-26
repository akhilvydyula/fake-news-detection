# =============================================================================
# Makefile — task shortcuts (same ideas as CI jobs).
#
# FRONTEND / UI FOCUS (no training)
#   You already have trained artifacts under artifacts/ — just run the app:
#       make install && make serve
#   Or one step on macOS / Linux / WSL (creates .venv if needed):
#       make setup && make serve
#
#   Open: http://127.0.0.1:8000/#dashboard
#   Aliases: make dev   or   make ui   (same as serve)
#
# TRAINING (optional, do later)
#   make train          # full pipeline
#   make train-quick    # smaller / reuse CSVs
#   make lab-train      # train-quick then serve (only if you need new weights)
#
# WINDOWS (PowerShell execution policy)
#   Prefer:  run.bat serve   or   run.bat setup
#   This Makefile needs `make` (e.g. Git Bash, WSL, or `choco install make`).
#
# Override Python:  make PYTHON=python3.11 serve
# Override port:    make serve PORT=8765   or   export NTP_PORT=8765 && make serve
# =============================================================================

.PHONY: help venv setup install train train-quick serve dev ui test doctor mlflow-ui lab-train stop restart

PYTHON ?= python
PORT ?= 8000

# Virtualenv interpreter (Unix / WSL / Git Bash). On Windows without bash, use run.bat.
VENV_PY := .venv/bin/python

help:
	@echo "UI + API (default path — no model training):"
	@echo "  make setup && make serve    # bootstrap venv + deps, then dashboard"
	@echo "  make serve  (aliases: dev, ui)  — set PORT=8765 to change; open http://127.0.0.1:PORT/#dashboard"
	@echo ""
	@echo "Optional training (when you want new artifacts):"
	@echo "  make train | make train-quick | make lab-train"
	@echo ""
	@echo "Other: make test | make doctor | make stop PORT=8000 | make restart | make install | make venv"

# Create only the virtualenv; then activate and make install (or use make setup).
venv:
	$(PYTHON) -m venv .venv
	@echo "Next: activate .venv (source .venv/bin/activate), then: make install && make serve"

# Bootstrap: create .venv if missing, install deps (Unix path to python).
setup: $(VENV_PY)
	$(VENV_PY) -m pip install -U pip
	$(VENV_PY) -m pip install -e ".[dev]"
	@echo "Setup done. Start UI: make serve   (training optional: make train)"

$(VENV_PY):
	$(PYTHON) -m venv .venv

# When venv is activated manually, PYTHON points at venv python.
install:
	$(PYTHON) -m pip install -U pip
	$(PYTHON) -m pip install -e ".[dev]"

# --- Training (optional) -------------------------------------------------------
train:
	$(PYTHON) -m src.pipeline.run_train

train-quick:
	$(PYTHON) -m src.pipeline.run_train --quick --skip-build

# Retrain then serve — only when you explicitly want a fresh quick train.
lab-train: train-quick serve

# --- App — dashboard + REST API (uses existing artifacts/) --------------------
serve:
	$(PYTHON) manage.py runserver 127.0.0.1:$(PORT)

dev: serve
ui: serve

# Unix: free the dashboard port (default PORT=8000). On Windows use: .\run.ps1 stop
stop:
	@P="$(PORT)"; \
	PIDS=$$(lsof -ti:$$P 2>/dev/null || true); \
	if [ -n "$$PIDS" ]; then echo "Stopping PID(s) on port $$P: $$PIDS"; kill -9 $$PIDS 2>/dev/null || true; else echo "Nothing listening on port $$P"; fi

restart: stop
	@sleep 1
	@$(MAKE) serve PORT=$(PORT)

# --- Quality / ops ------------------------------------------------------------
test:
	$(PYTHON) -m pytest -q

doctor:
	$(PYTHON) -m src.pipeline.doctor

mlflow-ui:
	$(PYTHON) -m mlflow ui --backend-store-uri ./mlruns
