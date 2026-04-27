"""Pydantic request/response shapes for HTTP APIs (shared by Django views)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class AnalyzeRequest(BaseModel):
    title: str = Field(default="", max_length=500)
    body: str = Field(default="", max_length=50_000)
    backend: Literal["classical", "bilstm", "mini_transformer"] = "classical"
    org_id: str = Field(default="demo-org", max_length=120)
    teacher_mode: bool = Field(
        default=False,
        description="If true, include precision/recall from last training run when available.",
    )


class AnalyzeUrlRequest(BaseModel):
    url: HttpUrl
    backend: Literal["classical", "bilstm", "mini_transformer"] = "classical"
    teacher_mode: bool = False
    org_id: str = Field(default="demo-org", max_length=120)


class V1AnalyzeRequest(BaseModel):
    """Unified payload for dashboard and partner integrations."""

    title: str = Field(default="", max_length=500)
    body: str = Field(default="", max_length=55_000)
    url: HttpUrl | None = None
    backend: Literal["classical", "bilstm", "mini_transformer"] = "classical"
    teacher_mode: bool = False
    org_id: str = Field(default="demo-org", max_length=120)


class InsightV1Request(BaseModel):
    """Paste or URL → classical TF–IDF insight (keywords + narratives). Same auth as /api/v1/analyze."""

    title: str = Field(default="", max_length=500)
    body: str = Field(default="", max_length=55_000)
    url: HttpUrl | None = None


class JobSubmitRequest(BaseModel):
    title: str = Field(default="", max_length=500)
    body: str = Field(default="", max_length=55_000)
    url: HttpUrl | None = None
    backend: Literal["classical", "bilstm", "mini_transformer"] = "classical"
    teacher_mode: bool = False
    org_id: str = Field(default="demo-org", max_length=120)
    force_async: bool = False


class CaseCreateRequest(BaseModel):
    title: str = Field(default="", max_length=500)
    article_text: str = Field(default="", max_length=55_000)
    severity: float = 0.0
    assignee: str = Field(default="", max_length=120)
    org_id: str = Field(default="demo-org", max_length=120)


class CasePatchRequest(BaseModel):
    state: Literal["NEW", "UNDER_REVIEW", "VERIFIED", "ESCALATED", "CLOSED"] | None = None
    assignee: str | None = Field(default=None, max_length=120)
