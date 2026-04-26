"""CORS — same environment variables as the previous FastAPI stack (CORS_ORIGINS, CORS_ALLOW_CREDENTIALS)."""

from __future__ import annotations

import os

from django.http import HttpRequest, HttpResponse


def _parse_origins() -> list[str]:
    raw = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
    if not raw:
        return ["*"]
    return raw


class CorsEnvMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self._origins = _parse_origins()
        self._allow_credentials = os.environ.get("CORS_ALLOW_CREDENTIALS", "").lower() in (
            "1",
            "true",
            "yes",
        )
        if any(o == "*" for o in self._origins):
            self._allow_credentials = False

    def _apply(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        origin = request.META.get("HTTP_ORIGIN") or request.META.get(
            "HTTP_ACCESS_CONTROL_REQUEST_ORIGIN"
        )
        if self._origins == ["*"] or len(self._origins) == 0:
            response["Access-Control-Allow-Origin"] = "*"
        elif origin and origin in self._origins:
            response["Access-Control-Allow-Origin"] = origin
        if self._allow_credentials and origin and origin in self._origins:
            response["Access-Control-Allow-Credentials"] = "true"
        response["Access-Control-Allow-Headers"] = "*"
        response["Access-Control-Allow-Methods"] = "*"
        return response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.method == "OPTIONS":
            r = HttpResponse()
            r.status_code = 200
            return self._apply(request, r)
        response = self.get_response(request)
        return self._apply(request, response)
