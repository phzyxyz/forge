"""WSGI entry — typical sync Django deploy path (gunicorn)."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "benchmarks.stack_press.apps.django_app.settings",
)

application = get_wsgi_application()
