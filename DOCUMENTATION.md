# Fake news detection — how to run everything

This guide is a **copy-paste runbook**. Run all commands from the **project root** (the folder that contains `pyproject.toml` and `src/`).

**Requirements:** Python **3.11+** (3.11 matches CI; 3.12/3.13 often work if TensorFlow installs). Internet access for Hugging Face datasets on first train.

### Windows: long paths & folder location

TensorFlow unpacks **very deep** paths. If `pip install` fails with **“No such file or directory”** and a long path under `.venv\Lib\site-packages\tensorflow\...`, do one of the following:

1. **Turn on long paths** (recommended): [Enable long paths in Windows](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation#enable-long-paths-in-windows-version-1607-and-later) (Group Policy *Enable Win32 long paths* or the registry `LongPathsEnabled` = `1`, then reboot).
2. **Move the repo** to a **short path**, e.g. `C:\dev\fake-news-detection` (avoids `OneDrive\Documents\...` length).

The repository already includes a **`.venv`** folder in `.gitignore`; create it locally (commands below)—it is **not** committed to Git.

### Launcher scripts (no `python -m …` by hand)

From the **project root**:

| Action | Windows | macOS / Linux / Git Bash |
|--------|---------|---------------------------|
| First-time venv + install | `run.bat setup` or `.\run.ps1 setup` | `chmod +x scripts/run.sh` then `./scripts/run.sh setup` |
| Train (full) | `run.bat train` | `./scripts/run.sh train` |
| Train (quick) | `run.bat train-quick` | `./scripts/run.sh train-quick` |
| **Start dashboard + API** | `run.bat serve` or double-click `run.bat` (starts **serve**) | `./scripts/run.sh serve` |
| Tests | `run.bat test` | `./scripts/run.sh test` |
| Artifact check | `run.bat doctor` | `./scripts/run.sh doctor` |

`run.bat` calls `run.ps1` with **Bypass** execution policy for that session. If `setup` fails on Windows, use **Python 3.11** (`py -3.11` available) or the manual venv steps in §1 below.

---

## 1. One-time setup

### Windows (PowerShell)

```powershell
cd "C:\path\to\fake-news-detection"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev]"
```

If execution policy blocks activation:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### macOS / Linux

```bash
cd /path/to/fake-news-detection
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -e ".[dev]"
```

### Alternative: only `requirements.txt`

```bash
pip install -r requirements.txt
pip install invoke   # optional, for tasks.py
```

---

## 2. Train models (data + classical + Keras)

**Full run** (~10k samples by default, downloads HF data):

```bash
python -m src.pipeline.run_train
```

**Faster smoke test** (smaller data, shorter Keras training; reuse CSVs if you already built data):

```bash
python -m src.pipeline.run_train --quick --skip-build
```

**Reuse existing CSVs** but full training settings:

```bash
python -m src.pipeline.run_train --skip-build
```

**With MLflow** (logs under `./mlruns` unless `MLFLOW_TRACKING_URI` is set):

```bash
python -m src.pipeline.run_train --mlflow
```

**Outputs:**

| Path | What |
|------|------|
| `data/processed/train.csv`, `val.csv`, `test.csv` | Splits |
| `artifacts/classical/logreg_tfidf.joblib` | Linear model |
| `artifacts/classical/keyword_hints.json` | Global keyword hints |
| `artifacts/keras_bilstm/model.keras` | BiLSTM |
| `artifacts/keras_mini_transformer/model.keras` | Small Transformer |
| `artifacts/metrics.json` | Train/val/test metrics + overfitting note |

---

## 3. Web app (API + friendly UI)

**Start the server:** `run.bat serve` / `.\run.ps1 serve` / `./scripts/run.sh serve`, **or**:

```bash
python -m uvicorn src.api.main:app --reload --host 127.0.0.1 --port 8000
```

Then open:

- **Product UI (dashboard, pricing, docs):** http://127.0.0.1:8000/ — analyzes via `POST /api/v1/analyze` (paste or `url` in JSON). Static assets live under `web/`. If the app is served under a subpath (reverse proxy), set `<html data-api-base="/your-prefix">` in `web/index.html` so the browser calls the correct API URLs.
- **Legacy teacher UI:** http://127.0.0.1:8000/classic — original paste/URL flow (`/api/analyze`, `/api/analyze-url`).
- **Interactive API docs:** http://127.0.0.1:8000/docs
- **Health:** http://127.0.0.1:8000/api/health — includes `api_key_required`, `auth_mode` (`anonymous` \| `single` \| `multi`), `brand`, artifact flags, and `usage_endpoint`.

**Optional environment variables (platform):**

- `PLATFORM_API_KEY` — single shared secret; clients send `X-API-Key`. Org id for metering defaults to `default`, or set `PLATFORM_DEFAULT_ORG_ID`.
- `PLATFORM_API_KEYS` — JSON object mapping each API key string to an org id, e.g. `{"sk_live_acme_xxx":"org_acme","sk_live_beta_yyy":"org_beta"}`. When this is set (non-empty after parse), it takes precedence over `PLATFORM_API_KEY` for v1 routes.
- `PLATFORM_USAGE_DB` — optional path to the SQLite file for request metering (default: `data/interim/platform_usage.sqlite`).
- `PLATFORM_BRAND_NAME` — shown in the health payload and product nav (e.g. your company name).

If `503` on analyze, train first (step 2) so `artifacts/` exists.

**Unified integration endpoint:** `POST /api/v1/analyze` with body `{"title":"...","body":"...","backend":"classical"}` or `{"url":"https://...","backend":"classical"}`. Response includes a `platform` block (summary, dimensions, `signal_cards`) for dashboards — deterministic scoring helpers you operate and tune, not third-party “agencies.” When authenticated, responses may include `tenant.org_id`.

**Usage metering:** `GET /api/v1/usage?days=30` with the same `X-API-Key` returns per-org counts of `POST /api/v1/analyze` calls (not available in anonymous demo mode).

**Legacy JSON:** `POST /api/analyze-url` with body `{"url":"https://...","backend":"classical","teacher_mode":false}` (use only where you may access the URL).

---

## 4. Command-line scoring (no browser)

```bash
python -m src.pipeline.predict_cli --text "Your headline. Your body text..." --backend classical
```

Backends: `classical`, `bilstm`, `mini_transformer`.

---

## 5. Shortcuts (Invoke — recommended on Windows)

After `pip install -e ".[dev]"` (includes Invoke):

```bash
invoke --list
invoke train
invoke train-quick
invoke serve
invoke test
invoke doctor       # artifact + UI paths (no TensorFlow import)
invoke lab          # train-quick then serve (blocks)
invoke mlflow-ui    # optional; separate terminal
```

**Operator runbook:** see `MAINTENANCE.md` (deploy checks, retrain, env vars).

**No `make` on Windows?** Use the table below: the **Invoke** column is the same job as **Make**.

---

## 6. Makefile commands (what each target does)

`make` is usually available in **Git Bash**, **WSL**, **macOS**, and **Linux**. In **PowerShell alone**, `make` is often missing—use **Invoke** instead (same effect).

| `make` target | What it runs | Use it when… |
|---------------|--------------|----------------|
| **`make venv`** | `python -m venv .venv` | You want only the virtualenv; then **activate** it and run **`make install`**. |
| **`make install`** | Upgrades `pip`, then `pip install -e ".[dev]"` | First time, or after pulling dependency changes. |
| **`make train`** | `python -m src.pipeline.run_train` | Full pipeline: download/build data (~10k rows default) + train all models. |
| **`make train-quick`** | `python -m src.pipeline.run_train --quick --skip-build` | Fast check: small run, **reuses** existing CSVs in `data/processed/`. |
| **`make setup`** | Creates `.venv` if missing, then `pip install -e ".[dev]"` (Unix path) | One-step bootstrap on macOS / Linux / WSL / Git Bash. |
| **`make serve`** | Starts **FastAPI** + UI with reload on port **8000** | Dashboard at http://127.0.0.1:8000/#dashboard (uses existing `artifacts/`). |
| **`make dev`** / **`make ui`** | Same as **`make serve`** | Shorthand when you only care about the front end. |
| **`make test`** | `pytest -q` | You changed code and want the same checks as CI. |
| **`make doctor`** | `python -m src.pipeline.doctor` | Quick JSON report: model files + `web/` / `static/` index (no TF import). |
| **`make mlflow-ui`** | `mlflow ui --backend-store-uri ./mlruns` | You ran training with `--mlflow` and want the experiment browser. |
| **`make lab-train`** | Runs **`train-quick`** then **`serve`** | Only when you want a quick retrain before the app; not the default UI path. |

**Custom Python:** `make PYTHON=python3.11 train` uses that interpreter for all targets.

**Typical flows**

```bash
make setup && make serve
```

```bash
make install && make serve
```

(Optional later: `make train` or `make lab-train` when you need new model files.)

Invoke equivalents: `invoke install`, `invoke train`, `invoke serve`, `invoke lab`, etc.

---

## 7. Tests (local CI parity)

```bash
pytest -q
```

---

## 8. MLflow UI (after a run with `--mlflow`)

```bash
python -m mlflow ui --backend-store-uri ./mlruns
```

Open the URL MLflow prints (usually http://127.0.0.1:5000).

---

## 9. Teaching notebooks

Open in Jupyter or VS Code:

1. `notebooks/01_teaching_walkthrough.ipynb`
2. `notebooks/02_metrics_and_overfitting.ipynb`

Set the notebook kernel to the same environment where you ran `pip install -e ".[dev]"`.

---

## 10. Security checks (optional, local)

```bash
pip install "bandit[toml]" pip-audit
bandit -r src -c bandit.yaml
pip install -e ".[dev]"
pip-audit --desc off
```

On **Windows**, prefer **`--desc off`** for `pip-audit` to avoid console Unicode errors.

---

## 11. Troubleshooting

| Problem | What to try |
|---------|-------------|
| `ModuleNotFoundError: No module named 'src'` | Run from project root; use `pip install -e ".[dev]"` or set `PYTHONPATH` to the repo root. |
| TensorFlow install fails | Use Python 3.11; see [tensorflow.org](https://www.tensorflow.org/install) for your OS. |
| First train is slow | Downloading HF datasets; rerun uses cache. |
| API slow to start | Importing TensorFlow is heavy; first request may be slow. |
| `pip-audit` exits 1 | Common on ML stacks; CI uploads JSON and uses a non-blocking policy by default—see README security section. |

---

## 12. GitHub (students pushing code)

- **CI** runs on `main` / `master` pushes and PRs: tests, Bandit, pip-audit artifact, CodeQL on schedule + PRs.
- Enable **Code scanning** / **Dependency graph** in the repo settings if your org allows it.

---

## 13. Where to read more

- **Project overview & ethics (BBC data):** [README.md](README.md)
- **This runbook:** you are here.
