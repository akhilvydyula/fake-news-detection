# Makefile — common in industry and C-heavy stacks; maps well to CI/CD "jobs".
# On Windows without `make`, use Invoke instead: `invoke train`, `invoke serve` (see README).
#
# Usage:
#   make venv       # create .venv only (then activate + make install)
#   make install    # editable install + dev tools (pytest, invoke)
#   make train
#   make serve      # then open http://127.0.0.1:8000
#   make test
#   make doctor   # artifact + UI paths (no TensorFlow)

.PHONY: venv install train train-quick serve test doctor mlflow-ui lab

PYTHON ?= python

venv:
	$(PYTHON) -m venv .venv
	@echo "Next: activate .venv, then run: make install"

install:
	$(PYTHON) -m pip install -U pip
	$(PYTHON) -m pip install -e ".[dev]"

train:
	$(PYTHON) -m src.pipeline.run_train

train-quick:
	$(PYTHON) -m src.pipeline.run_train --quick --skip-build

serve:
	$(PYTHON) -m uvicorn src.api.main:app --reload --host 127.0.0.1 --port 8000

test:
	$(PYTHON) -m pytest -q

doctor:
	$(PYTHON) -m src.pipeline.doctor

mlflow-ui:
	$(PYTHON) -m mlflow ui --backend-store-uri ./mlruns

# Smoke: refresh models on existing CSVs, then API (serve runs until Ctrl+C)
lab: train-quick serve
