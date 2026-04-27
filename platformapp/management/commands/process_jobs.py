from __future__ import annotations

import json
import logging
import time
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from src.api.schemas import V1AnalyzeRequest

from platformapp.jobs import run_analysis_job
from platformapp.models import AnalysisJob, WorkerHeartbeat

logger = logging.getLogger("newstrust.jobs")


def _claim_next_job() -> AnalysisJob | None:
    with transaction.atomic():
        job = AnalysisJob.objects.filter(status=AnalysisJob.Status.PENDING).order_by("submitted_at").first()
        if job is None:
            return None
        claimed = (
            AnalysisJob.objects.filter(id=job.id, status=AnalysisJob.Status.PENDING)
            .update(status=AnalysisJob.Status.PROCESSING, attempt_count=job.attempt_count + 1)
        )
        if claimed != 1:
            return None
        job.refresh_from_db()
        return job


class Command(BaseCommand):
    help = "Process queued analysis jobs."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--once", action="store_true", help="Process up to --max-jobs and exit.")
        parser.add_argument("--poll-interval", type=float, default=0.25, help="Seconds to wait between polls.")
        parser.add_argument("--max-jobs", type=int, default=1000, help="Max jobs processed in this invocation.")
        parser.add_argument("--worker-name", type=str, default="worker-1", help="Worker identity for heartbeat.")

    def handle(self, *args: Any, **options: Any) -> None:
        once = bool(options["once"])
        poll_interval = max(0.2, float(options["poll_interval"]))
        max_jobs = max(1, int(options["max_jobs"]))
        worker_name = str(options["worker_name"]).strip() or "worker-1"
        processed = 0

        logger.info("worker_started", extra={"worker_name": worker_name, "once": once})
        while True:
            WorkerHeartbeat.objects.update_or_create(worker_name=worker_name, defaults={})
            job = _claim_next_job()
            if job is None:
                if once or processed >= max_jobs:
                    break
                time.sleep(poll_interval)
                continue

            logger.info("job_processing_started", extra={"job_id": str(job.id), "org_id": job.org_id})
            req = V1AnalyzeRequest(
                title=job.title,
                body=job.body,
                url=job.url,
                backend=job.backend,
                teacher_mode=job.teacher_mode,
            )
            try:
                started = time.perf_counter()
                claimed_at = timezone.now()
                queue_wait_ms = max(
                    0,
                    int((claimed_at - job.submitted_at).total_seconds() * 1000),
                )
                result = run_analysis_job(req)
                result.setdefault("platform", {})
                result["platform"]["latency"] = {
                    "queue_wait_ms": queue_wait_ms,
                    "processing_ms": max(0, int((time.perf_counter() - started) * 1000)),
                }
                job.status = AnalysisJob.Status.SUCCEEDED
                job.processed_at = timezone.now()
                job.error = ""
                job.result_json = result
                job.save(update_fields=["status", "processed_at", "error", "result_json"])
                logger.info("job_processing_succeeded", extra={"job_id": str(job.id), "org_id": job.org_id})
            except Exception as exc:
                job.status = AnalysisJob.Status.FAILED
                job.processed_at = timezone.now()
                job.error = str(exc)
                job.save(update_fields=["status", "processed_at", "error"])
                logger.exception(
                    "job_processing_failed",
                    extra={"job_id": str(job.id), "org_id": job.org_id, "error": str(exc)},
                )
            processed += 1
            if once and processed >= max_jobs:
                break
            if processed >= max_jobs:
                break

        summary = {"processed_jobs": processed, "worker_name": worker_name, "once": once}
        self.stdout.write(self.style.SUCCESS(json.dumps(summary)))
