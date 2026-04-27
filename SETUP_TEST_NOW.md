# Setup and Test Now

## 1) Install and migrate

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
```

## 2) Run app + worker (two terminals)

Terminal A (API/UI):

```bash
python manage.py runserver 127.0.0.1:8000
```

Terminal B (queue worker loop):

```bash
python manage.py process_jobs
```

Optional env vars for this MVP:

```bash
set PLATFORM_ALERT_THRESHOLD=0.7
set PLATFORM_DEMO_SYNC_SMALL_JOBS=1
```

## 3) Run smoke tests

```bash
pytest -q tests/test_api.py -k "detect or cases or queue"
```

## 3-minute manual checklist

1. Open [http://127.0.0.1:8000/#dashboard](http://127.0.0.1:8000/#dashboard).
2. In **Input**, paste article text and click **Run analysis**; verify results render and `alert_recommended` appears for high risk.
3. In **Cases**, click **Create from current input text**.
4. Click **Refresh cases** and confirm the case appears for the selected org.
5. Update state to `UNDER_REVIEW` and assignee, click **Update case**, then confirm update persists.
6. Verify org scoping: change org id and confirm list changes.
7. Queue check: submit queue job and confirm status transitions in **Batch / Queue demo**.
