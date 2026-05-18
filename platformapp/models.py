from __future__ import annotations

import uuid

from django.db import models


class AnalysisJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org_id = models.CharField(max_length=120, default="demo-org")
    title = models.CharField(max_length=500, blank=True, default="")
    body = models.TextField(blank=True, default="")
    url = models.URLField(blank=True, null=True)
    backend = models.CharField(max_length=32, default="classical")
    teacher_mode = models.BooleanField(default=False)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    error = models.TextField(blank=True, default="")
    result_json = models.JSONField(blank=True, null=True)
    attempt_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-submitted_at"]
        indexes = [
            models.Index(fields=["status", "submitted_at"]),
            models.Index(fields=["org_id", "submitted_at"]),
        ]


class WorkerHeartbeat(models.Model):
    worker_name = models.CharField(max_length=120, unique=True)
    last_seen_at = models.DateTimeField(auto_now=True)


class Case(models.Model):
    class State(models.TextChoices):
        NEW = "NEW", "New"
        UNDER_REVIEW = "UNDER_REVIEW", "Under review"
        VERIFIED = "VERIFIED", "Verified"
        ESCALATED = "ESCALATED", "Escalated"
        CLOSED = "CLOSED", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org_id = models.CharField(max_length=120, default="demo-org")
    title = models.CharField(max_length=500, blank=True, default="")
    article_text = models.TextField(blank=True, default="")
    state = models.CharField(max_length=20, choices=State.choices, default=State.NEW)
    assignee = models.CharField(max_length=120, blank=True, default="")
    severity = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["org_id", "updated_at"]),
            models.Index(fields=["org_id", "state"]),
        ]


class CaseEvent(models.Model):
    id = models.BigAutoField(primary_key=True)
    case = models.ForeignKey(Case, related_name="events", on_delete=models.CASCADE)
    org_id = models.CharField(max_length=120, default="demo-org")
    event_type = models.CharField(max_length=40)
    old_value = models.CharField(max_length=200, blank=True, default="")
    new_value = models.CharField(max_length=200, blank=True, default="")
    actor = models.CharField(max_length=120, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["case", "created_at"]),
            models.Index(fields=["org_id", "created_at"]),
        ]


class RSSFeed(models.Model):
    """Configured RSS source for scheduled ingestion."""

    name = models.CharField(max_length=160)
    url = models.URLField(unique=True)
    is_active = models.BooleanField(default=True)
    org_id = models.CharField(max_length=120, default="demo-org")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_fetched_at = models.DateTimeField(blank=True, null=True)
    last_error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active", "updated_at"]),
            models.Index(fields=["org_id", "is_active"]),
        ]

    def __str__(self) -> str:
        return self.name or self.url


class ScoredArticle(models.Model):
    """Article captured from RSS and scored with the existing model stack."""

    class Prediction(models.TextChoices):
        LIKELY_RELIABLE = "likely_reliable", "Likely reliable"
        UNCERTAIN = "uncertain", "Uncertain"
        REVIEW_RECOMMENDED = "review_recommended", "Review recommended"
        MODEL_UNAVAILABLE = "model_unavailable", "Model unavailable"
        FAILED = "failed", "Failed"

    feed = models.ForeignKey(RSSFeed, related_name="articles", on_delete=models.CASCADE)
    org_id = models.CharField(max_length=120, default="demo-org")
    source_id = models.CharField(max_length=700)
    url = models.URLField(max_length=1000, blank=True, default="")
    title = models.CharField(max_length=500, blank=True, default="")
    summary = models.TextField(blank=True, default="")
    content = models.TextField(blank=True, default="")
    published_at = models.DateTimeField(blank=True, null=True)
    ingested_at = models.DateTimeField(auto_now_add=True)
    scored_at = models.DateTimeField(blank=True, null=True)
    backend = models.CharField(max_length=32, default="classical")
    prediction = models.CharField(
        max_length=32,
        choices=Prediction.choices,
        default=Prediction.UNCERTAIN,
    )
    confidence = models.FloatField(default=0.0)
    flagged_for_review = models.BooleanField(default=False)
    result_json = models.JSONField(blank=True, null=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-published_at", "-ingested_at"]
        constraints = [
            models.UniqueConstraint(fields=["feed", "source_id"], name="uniq_feed_source_article"),
        ]
        indexes = [
            models.Index(fields=["org_id", "flagged_for_review", "scored_at"]),
            models.Index(fields=["feed", "published_at"]),
            models.Index(fields=["prediction", "confidence"]),
        ]

    def __str__(self) -> str:
        return self.title or self.url or self.source_id
