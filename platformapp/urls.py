from __future__ import annotations

from django.urls import path

from . import views

urlpatterns = [
    path("", views.platform_index, name="platform_index"),
    path("classic", views.classic_index, name="classic_index"),
    path("assets/<str:asset_name>", views.platform_asset, name="platform_asset"),
    path("api/health", views.api_health, name="api_health"),
    path("api/model-info", views.api_model_info, name="api_model_info"),
    path("api/v1/analyze", views.api_v1_analyze, name="api_v1_analyze"),
    path("api/v1/insight", views.api_v1_insight, name="api_v1_insight"),
    path("api/v1/usage", views.api_v1_usage, name="api_v1_usage"),
    path("api/v1/jobs", views.api_v1_jobs_list, name="api_v1_jobs_list"),
    path("api/v1/jobs/submit", views.api_v1_jobs_submit, name="api_v1_jobs_submit"),
    path("api/v1/jobs/<uuid:job_id>", views.api_v1_jobs_status, name="api_v1_jobs_status"),
    path("api/analyze", views.api_analyze, name="api_analyze"),
    path("api/analyze-url", views.api_analyze_url, name="api_analyze_url"),
]
