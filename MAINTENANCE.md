# Operating and maintaining this platform

You run this stack yourself: training, deployment, API keys, and thresholds. There are no external “agencies” or autonomous orgs in the product—only **your** models, **your** `signal_cards` logic in `src/service/enrichment.py`, and **your** infrastructure.

## Daily / on deploy

1. **Health:** `GET /api/health` — `artifacts`, `api_key_required`, `auth_mode`, `brand`, `usage_endpoint`.
2. **Artifacts:** `make doctor` or `invoke doctor` — confirms classical weights, optional Keras files, `web/index.html`, and `metrics.json` without importing TensorFlow.
3. **API smoke:** `POST /api/v1/analyze` with a short paste payload (see `DOCUMENTATION.md`).

## When to retrain

- You expanded or relabeled data and want scores to match your newsroom.
- Metrics drift: spot-check false positives/negatives and adjust training data or thresholds in your integration layer.

Commands: `make train` or `invoke train` (full); `make train-quick` for a smoke run on existing CSVs.

## Configuration you own

| Variable | Role |
|----------|------|
| `PLATFORM_API_KEY` | Single secret; v1 routes require `X-API-Key`; metering org defaults to `default` or `PLATFORM_DEFAULT_ORG_ID`. |
| `PLATFORM_API_KEYS` | JSON map of `api_key` → `org_id` for multi-tenant keys and isolated usage stats. |
| `PLATFORM_USAGE_DB` | Optional SQLite path for metering (`data/interim/platform_usage.sqlite` by default). |
| `PLATFORM_BRAND_NAME` | Shown in health + product nav. |
| `CORS_ORIGINS` | Comma-separated allowed origins (default `*`). |

## Security and compliance

- URL fetch: respect robots/terms; `fetch_url_text` uses size limits and host blocks—review `src/ingest/fetch_url.py` for your policy.
- Customer payloads: default path is **inference only**; retention and fine-tuning are explicit product decisions on your side.

## CI / quality

- `make test` or `invoke test` — pytest.
- Use the same checks in GitHub Actions / GitLab CI as documented in the repo.

## UI entry points

- **Product shell:** `/` → `web/`
- **Legacy teacher UI:** `/classic` → `static/`

To change dashboard copy or scoring narratives, edit `web/` and `src/service/enrichment.py`; the API field is `platform.signal_cards` (`schema_version` `1.1`).
