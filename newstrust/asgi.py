"""ASGI config for newstrust."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "newstrust.settings")

application = get_asgi_application()
