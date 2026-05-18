# =============================================================================
# Makefile — task shortcuts (same ideas as CI jobs).
#
# FRONTEND / UI FOCUS (no training)
#   You already have trained artifacts under artifacts/ — just run the app:
#       make install && make streamlit
#   Or one step on macOS / Linux / WSL (creates .venv if needed):
#       make setup && make streamlit
#
#   Open: http://localhost:8501/?demo=1
#   Aliases: make product   or   make streamlit-ui
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

.PHONY: help venv setup install migrate score-feeds train train-quick serve dev ui run streamlit streamlit-ui product test doctor mlflow-ui lab-train stop restart

PYTHON ?= $(if $(wildcard .venv/Scripts/python.exe),.venv/Scripts/python.exe,$(if $(wildcard .venv/bin/python),.venv/bin/python,python))
PORT ?= 8000

# Virtualenv interpreter (Windows first, then Unix / WSL / Git Bash).
VENV_PY := $(if $(wildcard .venv/Scripts/python.exe),.venv/Scripts/python.exe,.venv/bin/python)

help:
	@echo "Streamlit product UI (recommended; no model training):"
	@echo "  make setup && make streamlit    # bootstrap venv + deps, then product UI"
	@echo "  make run                        # same as make streamlit; open http://localhost:8501/?demo=1"
	@echo "  make streamlit                  # open http://localhost:8501/?demo=1"
	@echo ""
	@echo "Legacy local server:"
	@echo "  make serve  (aliases: dev, ui)  — set PORT=8765 to change; open http://127.0.0.1:PORT/#dashboard"
	@echo ""
	@echo "Optional training (when you want new artifacts):"
	@echo "  make train | make train-quick | make lab-train"
	@echo ""
	@echo "RSS pipeline: make migrate && make score-feeds"
	@echo "Other: make test | make doctor | make stop PORT=8000 | make restart | make install | make venv"

# Create only the virtualenv; then activate and make install (or use make setup).
venv:
	$(PYTHON) -m venv .venv
	@echo "Next: activate .venv (source .venv/bin/activate), then: make install && make streamlit"

# Bootstrap: create .venv if missing, install deps (Unix path to python).
setup: $(VENV_PY)
	$(VENV_PY) -m pip install -U pip
	$(VENV_PY) -m pip install -e ".[dev]"
	@echo "Setup done. Start Streamlit UI: make streamlit   (training optional: make train)"

$(VENV_PY):
	$(PYTHON) -m venv .venv

# When venv is activated manually, PYTHON points at venv python.
install:
	$(PYTHON) -m pip install -U pip
	$(PYTHON) -m pip install -e ".[dev]"

migrate:
	$(PYTHON) manage.py migrate

score-feeds:
	$(PYTHON) manage.py score_feeds --seed

# --- Training (optional) -------------------------------------------------------
train:
	$(PYTHON) -m src.pipeline.run_train

train-quick:
	$(PYTHON) -m src.pipeline.run_train --quick --skip-build

# Retrain then serve — only when you explicitly want a fresh quick train.
lab-train: train-quick serve

# --- Streamlit product UI (recommended MVP; uses existing artifacts/) ----------
streamlit:
	$(PYTHON) -m streamlit run streamlit_app.py --server.port 8501 --browser.gatherUsageStats false

run: streamlit
streamlit-ui: streamlit
product: streamlit

# --- Legacy app — dashboard + REST API (uses existing artifacts/) -------------
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
