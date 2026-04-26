from __future__ import annotations

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AnalysisJob",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("org_id", models.CharField(default="demo-org", max_length=120)),
                ("title", models.CharField(blank=True, default="", max_length=500)),
                ("body", models.TextField(blank=True, default="")),
                ("url", models.URLField(blank=True, null=True)),
                ("backend", models.CharField(default="classical", max_length=32)),
                ("teacher_mode", models.BooleanField(default=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("processing", "Processing"),
                            ("succeeded", "Succeeded"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("error", models.TextField(blank=True, default="")),
                ("result_json", models.JSONField(blank=True, null=True)),
                ("attempt_count", models.PositiveIntegerField(default=0)),
            ],
            options={"ordering": ["-submitted_at"]},
        ),
        migrations.CreateModel(
            name="WorkerHeartbeat",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("worker_name", models.CharField(max_length=120, unique=True)),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddIndex(
            model_name="analysisjob",
            index=models.Index(fields=["status", "submitted_at"], name="platformapp__status_09b072_idx"),
        ),
        migrations.AddIndex(
            model_name="analysisjob",
            index=models.Index(fields=["org_id", "submitted_at"], name="platformapp__org_id_9f8516_idx"),
        ),
    ]
