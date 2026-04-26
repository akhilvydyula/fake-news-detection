from __future__ import annotations

from django.urls import include, path, re_path
from django.views.static import serve

from src.config import PROJECT_ROOT

urlpatterns = [path("", include("platformapp.urls"))]

# Legacy: same as previous FastAPI mount of static/ (when the directory exists).
_static = PROJECT_ROOT / "static"
if _static.is_dir():
    urlpatterns += [
        re_path(r"^static/(?P<path>.*)$", serve, {"document_root": str(_static)}),
    ]
