"""WSGI config for newstrust."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "newstrust.settings")

application = get_wsgi_application()
