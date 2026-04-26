# GitLab CI/CD — setup, “why no pipeline?”, and local debugging

This repository **also** contains `.github/workflows/` for **GitHub**. **GitLab does not run those files.**  
On GitLab, only **`.gitlab-ci.yml`** (in the repo root) defines pipelines.

---

## 1. Quick checklist (pipelines not showing)

| Check | What to do |
|--------|------------|
| **Wrong host** | Confirm the remote is **GitLab** (`git remote -v`), not only GitHub. Pushing to GitHub will **not** trigger GitLab pipelines. |
| **Missing file** | Ensure **`.gitlab-ci.yml`** is committed and pushed to the branch you care about. |
| **Default branch** | The **workflow** runs on **merge requests** and on pushes to **`$CI_DEFAULT_BRANCH`** (often `main` or `master`). Pushes to other branches only get a pipeline if you open an **MR** from that branch. |
| **CI disabled** | **Settings → General → Visibility** (or **CI/CD → General pipelines**) — ensure pipelines are not disabled. |
| **No runners** | **Settings → CI/CD → Runners** — you need **shared runners** enabled (GitLab.com) or a **project/group runner** online. If there are no runners, jobs stay *pending* forever. |
| **Invalid YAML** | **Build → Pipeline editor** → **Validate**, or **CI/CD → Pipelines → Run pipeline** and read the error. |

---

## 2. What this project’s pipeline does

| Stage | Job | Purpose |
|--------|-----|---------|
| `test` | `test` | `pip install -e ".[dev]"`, `python manage.py check`, `pytest` |
| `security` | `dependency_audit` | `pip-audit` (+ JSON artifact). **`allow_failure: true`** so known ML transitive CVEs do not block teaching. |
| `security` | `bandit_sast` | **Bandit** on `src/`; fails on medium+ issues (like GitHub). **`bandit-results.json`** in job artifacts. |

---

## 3. GitLab CLI (`glab`) vs GitLab Runner

| Tool | Role |
|------|------|
| **`glab`** | Talks to **GitLab API** (list pipelines, logs, MRs). It does **not** execute jobs on your laptop as the real runner. |
| **`gitlab-runner`** | Binary that **runs** `.gitlab-ci.yml` jobs (on your machine or a server). Used for **local exec** or self-hosted runners. |

Install `glab`: see [GitLab CLI](https://gitlab.com/gitlab-org/cli).

```bash
glab auth login --hostname gitlab.com
glab ci status
glab ci view
```

---

## 4. Validate and debug from your laptop

### A) Lint the CI file (official API)

Replace `PROJECT_ID` and `TOKEN` (scope: `api`):

```bash
curl --header "Content-Type: application/json" \
  "https://gitlab.com/api/v4/projects/PROJECT_ID/ci/lint" \
  --data-urlencode "content@.gitlab-ci.yml"
```

Easier: in GitLab UI → **Build → Pipeline editor** → paste → **Validate**.

### B) Run the **same commands** as CI (fastest feedback)

From the repo root, use the same image mentally as CI (`python:3.11-bookworm`), or your local 3.11:

```bash
python -m pip install -U pip
pip install -e ".[dev]"
python manage.py check
pytest -q
```

Security jobs:

```bash
pip install pip-audit "bandit[toml]"
pip install -e ".[dev]"
pip-audit --desc off
bandit -r src -c bandit.yaml --severity-level medium --confidence-level medium
```

If this passes locally but fails in GitLab, compare **Python version**, **OS**, and **job logs**.

### C) `gitlab-runner exec` (run one job locally)

Requires [GitLab Runner](https://docs.gitlab.com/runner/install/) installed and a shell/docker executor.

```bash
gitlab-runner exec docker test
```

You need a valid local `config.toml` and Docker; this is closer to “real” CI but heavier.

### D) Community: `gitlab-ci-local` (optional)

Third-party tools can approximate pipelines locally; search for **gitlab-ci-local** and follow their docs (Docker-based).

---

## 5. US / region / SaaS

**GitLab.com** runs in cloud regions; “US side” in the UI is usually **your account region / URL** (`gitlab.com` vs self-managed). Pipelines are **not** tied to GitHub Actions; if the project lives on **GitHub**, you will **never** see these jobs on GitLab until you **mirror** or **push a copy** to GitLab with this `.gitlab-ci.yml`.

---

## 6. Teaching tip

- **GitHub class:** use `.github/workflows/`.  
- **GitLab class:** use `.gitlab-ci.yml` (this file).  
Same *ideas* (stages, artifacts, allow_failure); different YAML syntax and UI.

For the full project runbook (venv, Make, training), see [DOCUMENTATION.md](DOCUMENTATION.md).
