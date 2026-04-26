"""
Django views: platform UI + legacy UI + JSON APIs.
API POSTs are CSRF-exempt; production should use X-API-Key / tokens and drop exempt if using session CSRF.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx
from django.http import (
    FileResponse,
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseNotAllowed,
    JsonResponse,
)
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from pydantic import ValidationError

from src.api.deps import PlatformAPIError, auth_configured, auth_mode, resolve_platform_auth
from src.api.schemas import (
    AnalyzeRequest,
    AnalyzeUrlRequest,
    InsightV1Request,
    JobSubmitRequest,
    V1AnalyzeRequest,
)
from src.api.usage_store import log_usage, usage_summary
from src.config import PROJECT_ROOT
from src.ingest.fetch_url import fetch_url_text
from src.service.enrichment import enrich_platform_payload
from src.service.news_insight import build_text_insight
from src.service.predictor import (
    _keyword_hints,
    artifacts_ready,
    build_api_response,
    build_full_text,
    load_metrics_json,
    product_framing,
)
from .operations import (
    brand_name,
    compliance_url_note,
    resolve_text_and_source,
)
from .models import AnalysisJob, WorkerHeartbeat

STATIC_DIR = PROJECT_ROOT / "static"
WEB_DIR = PROJECT_ROOT / "web"
logger = logging.getLogger("newstrust.api")

_PLATFORM_ASSET_MEDIA: dict[str, str] = {
    "platform.js": "application/javascript; charset=utf-8",
    "platform.css": "text/css; charset=utf-8",
}


def _get_api_key(request: HttpRequest) -> str | None:
    return request.META.get("HTTP_X_API_KEY")


def _json_error(detail: str, status: int) -> JsonResponse:
    return JsonResponse({"detail": detail}, status=status)


@csrf_exempt
def platform_asset(request: HttpRequest, asset_name: str) -> FileResponse | JsonResponse:
    if request.method != "GET":
        return _method_not_allowed(["GET"])
    if asset_name not in _PLATFORM_ASSET_MEDIA:
        return _json_error("Unknown asset", 404)
    path = WEB_DIR / "assets" / asset_name
    if not path.is_file():
        return _json_error(f"Missing file: {path.name} under web/assets/", 404)
    return FileResponse(path.open("rb"), content_type=_PLATFORM_ASSET_MEDIA[asset_name])


def _method_not_allowed(allowed: list[str]) -> HttpResponse:
    r = HttpResponseNotAllowed(allowed)
    r["Allow"] = ", ".join(allowed)
    return r


def api_health(_request: HttpRequest) -> JsonResponse:
    ready = artifacts_ready()
    backlog = AnalysisJob.objects.filter(status=AnalysisJob.Status.PENDING).count()
    latest_heartbeat = WorkerHeartbeat.objects.order_by("-last_seen_at").first()
    return JsonResponse(
        {
            "status": "ok" if any(ready.values()) else "no_models",
            "artifacts": ready,
            "api_key_required": auth_configured(),
            "auth_mode": auth_mode(),
            "brand": os.environ.get("PLATFORM_BRAND_NAME", "News Trust Platform"),
            "usage_endpoint": "/api/v1/usage",
            "queue": {
                "backlog": backlog,
                "latest_worker": (
                    {
                        "worker_name": latest_heartbeat.worker_name,
                        "last_seen_at": latest_heartbeat.last_seen_at.isoformat(),
                        "seconds_since_seen": int(
                            (timezone.now() - latest_heartbeat.last_seen_at).total_seconds()
                        ),
                    }
                    if latest_heartbeat
                    else None
                ),
            },
        }
    )


def api_model_info(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return _method_not_allowed(["GET"])
    teacher = request.GET.get("teacher_mode", "").lower() in ("1", "true", "yes")
    metrics = load_metrics_json()
    hints = _keyword_hints()
    base: dict[str, Any] = {
        "what_this_does": (
            "This tool compares your draft to patterns in a research dataset. "
            "It does not verify facts, names, or dates. Always use normal journalism checks."
        ),
        "product_framing": product_framing(),
        "artifacts": artifacts_ready(),
        "v1_endpoint": "/api/v1/analyze",
        "insight_endpoint": "/api/v1/insight",
    }
    if teacher and metrics:
        base["training_metrics"] = metrics
        base["overfitting_note"] = metrics.get("overfitting_note")
    if teacher and hints:
        base["global_keyword_hints"] = {
            "note": hints.get("note"),
            "examples_pushed_toward_review_in_training": hints.get(
                "ngrams_associated_with_predicted_fake", []
            )[:15],
        }
    return JsonResponse(base)


@csrf_exempt
def api_v1_analyze(request: HttpRequest) -> JsonResponse | HttpResponse:
    if request.method != "POST":
        return _method_not_allowed(["POST"])
    try:
        data = json.loads(request.body)
        req = V1AnalyzeRequest.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as e:
        if isinstance(e, ValidationError):
            return JsonResponse({"detail": e.errors()}, status=422)
        return _json_error("Invalid JSON", 400)

    try:
        auth = resolve_platform_auth(_get_api_key(request))
    except PlatformAPIError as e:
        return _json_error(e.detail, e.status_code)

    status = 200
    logger.info("analyze_request_received", extra={"path": "/api/v1/analyze", "method": request.method})
    try:
        text, src = resolve_text_and_source(req)
        if len(text.strip()) < 20:
            raise PlatformAPIError(
                400, "Text too short after resolving URL or paste."
            )
        base = build_api_response(text, req.backend, req.teacher_mode)
        if base is None:
            raise PlatformAPIError(
                503, "Model files are missing. Run: python -m src.pipeline.run_train"
            )
        out = enrich_platform_payload(base, text, req.backend)
        out["source"] = src
        out["platform"]["brand_hint"] = brand_name()
        if auth.org_id is not None:
            out["tenant"] = {"org_id": auth.org_id}
        logger.info("analyze_request_succeeded", extra={"path": "/api/v1/analyze", "status": 200})
        return JsonResponse(out)
    except PlatformAPIError as e:
        status = e.status_code
        logger.info("analyze_request_failed", extra={"path": "/api/v1/analyze", "status": e.status_code})
        return _json_error(e.detail, e.status_code)
    finally:
        if auth.org_id is not None:
            log_usage(auth.org_id, "/api/v1/analyze", status)


@csrf_exempt
def api_v1_insight(request: HttpRequest) -> JsonResponse | HttpResponse:
    if request.method != "POST":
        return _method_not_allowed(["POST"])
    try:
        data = json.loads(request.body)
        body_req = InsightV1Request.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as e:
        if isinstance(e, ValidationError):
            return JsonResponse({"detail": e.errors()}, status=422)
        return _json_error("Invalid JSON", 400)

    try:
        auth = resolve_platform_auth(_get_api_key(request))
    except PlatformAPIError as e:
        return _json_error(e.detail, e.status_code)


def _job_to_dict(job: AnalysisJob) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "job_id": str(job.id),
        "org_id": job.org_id,
        "status": job.status,
        "backend": job.backend,
        "teacher_mode": job.teacher_mode,
        "submitted_at": job.submitted_at.isoformat(),
        "processed_at": job.processed_at.isoformat() if job.processed_at else None,
        "error": job.error or None,
    }
    if job.result_json:
        result = job.result_json
        platform = (result or {}).get("platform", {})
        dims = platform.get("dimensions", {})
        cards = platform.get("signal_cards", [])
        payload["result"] = {
            "score_toward_review_0_to_1": result.get("score_toward_review_0_to_1"),
            "summary": platform.get("article_summary"),
            "composite_attention_0_to_1": dims.get("composite_attention_0_to_1"),
            "top_signals": [c.get("title", "") for c in cards[:3]],
            "raw": result,
        }
    return payload


@csrf_exempt
def api_v1_jobs_submit(request: HttpRequest) -> JsonResponse | HttpResponse:
    if request.method != "POST":
        return _method_not_allowed(["POST"])
    try:
        data = json.loads(request.body)
        req = JobSubmitRequest.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as e:
        if isinstance(e, ValidationError):
            return JsonResponse({"detail": e.errors()}, status=422)
        return _json_error("Invalid JSON", 400)

    org_id = (req.org_id or "demo-org").strip() or "demo-org"
    job = AnalysisJob.objects.create(
        org_id=org_id,
        title=req.title,
        body=req.body,
        url=str(req.url) if req.url else None,
        backend=req.backend,
        teacher_mode=req.teacher_mode,
        status=AnalysisJob.Status.PENDING,
    )
    logger.info(
        "job_submitted",
        extra={"job_id": str(job.id), "org_id": org_id, "backend": req.backend},
    )
    return JsonResponse(
        {
            "job_id": str(job.id),
            "status": job.status,
            "org_id": job.org_id,
            "submitted_at": job.submitted_at.isoformat(),
            "status_url": f"/api/v1/jobs/{job.id}",
        },
        status=202,
    )


def api_v1_jobs_status(request: HttpRequest, job_id: Any) -> JsonResponse | HttpResponse:
    if request.method != "GET":
        return _method_not_allowed(["GET"])
    try:
        job = AnalysisJob.objects.get(id=job_id)
    except AnalysisJob.DoesNotExist:
        return _json_error("Job not found.", 404)
    return JsonResponse(_job_to_dict(job))


def api_v1_jobs_list(request: HttpRequest) -> JsonResponse | HttpResponse:
    if request.method != "GET":
        return _method_not_allowed(["GET"])
    org_id = (request.GET.get("org_id", "demo-org") or "demo-org").strip() or "demo-org"
    jobs = AnalysisJob.objects.filter(org_id=org_id).order_by("-submitted_at")[:20]
    return JsonResponse(
        {
            "org_id": org_id,
            "count": len(jobs),
            "jobs": [_job_to_dict(job) for job in jobs],
        }
    )

    status = 200
    logger.info("insight_request_received", extra={"path": "/api/v1/insight", "method": request.method})
    try:
        wrapped = V1AnalyzeRequest(
            title=body_req.title,
            body=body_req.body,
            url=body_req.url,
            backend="classical",
            teacher_mode=False,
        )
        text, src = resolve_text_and_source(wrapped)
        if len(text.strip()) < 20:
            raise PlatformAPIError(
                400, "Text too short after resolving URL or paste."
            )
        out = build_text_insight(text)
        if out is None:
            raise PlatformAPIError(
                503, "Model files are missing. Run: python -m src.pipeline.run_train"
            )
        out["source"] = src
        out["platform_brand"] = brand_name()
        if auth.org_id is not None:
            out["tenant"] = {"org_id": auth.org_id}
        logger.info("insight_request_succeeded", extra={"path": "/api/v1/insight", "status": 200})
        return JsonResponse(out)
    except PlatformAPIError as e:
        status = e.status_code
        logger.info("insight_request_failed", extra={"path": "/api/v1/insight", "status": e.status_code})
        return _json_error(e.detail, e.status_code)
    finally:
        if auth.org_id is not None:
            log_usage(auth.org_id, "/api/v1/insight", status)


def api_v1_usage(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return _method_not_allowed(["GET"])
    try:
        days = int(request.GET.get("days", "30"))
    except (TypeError, ValueError):
        days = 30
    try:
        auth = resolve_platform_auth(_get_api_key(request))
    except PlatformAPIError as e:
        return _json_error(e.detail, e.status_code)
    if auth.org_id is None:
        return _json_error(
            "Usage reporting requires API keys. Set PLATFORM_API_KEY or PLATFORM_API_KEYS on the server.",
            401,
        )
    return JsonResponse(usage_summary(auth.org_id, days=min(max(days, 1), 366)))


@csrf_exempt
def api_analyze(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return _method_not_allowed(["POST"])
    try:
        data = json.loads(request.body)
        req = AnalyzeRequest.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as e:
        if isinstance(e, ValidationError):
            return JsonResponse({"detail": e.errors()}, status=422)
        return _json_error("Invalid JSON", 400)

    try:
        text = build_full_text(req.title, req.body)
        if len(text.strip()) < 20:
            raise PlatformAPIError(
                400,
                "Please enter a longer headline or article snippet (at least ~20 characters).",
            )
        out = build_api_response(text, req.backend, req.teacher_mode)
        if out is None:
            raise PlatformAPIError(
                503, "Model files are missing. Run: python -m src.pipeline.run_train"
            )
        out["source"] = {"type": "paste"}
        return JsonResponse(out)
    except PlatformAPIError as e:
        return _json_error(e.detail, e.status_code)


@csrf_exempt
def api_analyze_url(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return _method_not_allowed(["POST"])
    try:
        data = json.loads(request.body)
        req = AnalyzeUrlRequest.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as e:
        if isinstance(e, ValidationError):
            return JsonResponse({"detail": e.errors()}, status=422)
        return _json_error("Invalid JSON", 400)

    try:
        try:
            text, meta = fetch_url_text(str(req.url))
        except ValueError as e:
            raise PlatformAPIError(400, str(e)) from e
        except httpx.HTTPError as e:
            raise PlatformAPIError(502, f"Could not fetch URL: {e}") from e

        if len(text.strip()) < 20:
            raise PlatformAPIError(400, "Extracted text too short.")
        out = build_api_response(text, req.backend, req.teacher_mode)
        if out is None:
            raise PlatformAPIError(
                503, "Model files are missing. Run: python -m src.pipeline.run_train"
            )
        out["source"] = {
            "type": "url",
            **meta,
            "compliance_note": compliance_url_note(),
        }
        return JsonResponse(out)
    except PlatformAPIError as e:
        return _json_error(e.detail, e.status_code)


def platform_index(request: HttpRequest) -> FileResponse:
    if request.method != "GET":
        return _method_not_allowed(["GET"])
    index_path = WEB_DIR / "index.html"
    if not index_path.is_file():
        index_path = STATIC_DIR / "index.html"
    if not index_path.is_file():
        raise Http404("web/index.html missing")
    return FileResponse(
        index_path.open("rb"), content_type="text/html; charset=utf-8"
    )


def classic_index(request: HttpRequest) -> FileResponse:
    if request.method != "GET":
        return _method_not_allowed(["GET"])
    p = STATIC_DIR / "index.html"
    if not p.is_file():
        raise Http404("legacy UI missing")
    return FileResponse(p.open("rb"), content_type="text/html; charset=utf-8")
