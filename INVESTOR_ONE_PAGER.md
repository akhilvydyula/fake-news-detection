# Investor One-Pager: News Trust Platform

## Value proposition
News Trust Platform helps editorial and trust/safety teams triage article risk in minutes, not hours. It combines ML scoring, concise explainability, and queue-based operations so teams can review more content without sacrificing human judgment.

## What is demoable today
- Web dashboard for synchronous article analysis (paste or URL)
- Async queue pipeline with job submission, worker processing, and status/result retrieval
- Tenant/org id support for multi-organization workflows
- Health endpoint exposing model readiness, queue backlog, and worker heartbeat

## Architecture snapshot
- **API/UI:** Django app serving product dashboard + JSON API
- **ML inference path:** existing scoring + enrichment + insight modules
- **Queue layer:** `AnalysisJob` model in SQL database with audit fields
- **Worker:** Django management command (`process_jobs`) for background execution
- **Observability hooks:** structured lifecycle logs + queue health telemetry

## Why this matters for go-to-market
- **Fast pilot onboarding:** single deployable stack, no heavy orchestrator required
- **Enterprise readiness path:** queue contract can move to Celery/Redis/Kafka with minimal API change
- **Compliance and control:** org-aware records, job history, and explicit processing timestamps

## Scalability path (next phases)
1. Replace DB polling worker with distributed task broker (Celery + Redis/RabbitMQ)
2. Add RBAC, per-tenant quotas, and signed webhook callbacks
3. Introduce managed Postgres + centralized logs/metrics
4. Expand model registry and A/B routing across model backends
