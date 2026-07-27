import os

from django.core.asgi import get_asgi_application

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "benchmarks.stack_press.apps.django_app.settings",
)

application = get_asgi_application()
