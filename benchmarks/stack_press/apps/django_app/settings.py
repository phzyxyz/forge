"""Minimal Django settings for stack press (ASGI)."""

from __future__ import annotations

import os

SECRET_KEY = "bench-only-not-secret"
DEBUG = False
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "benchmarks.stack_press.apps.django_app",
]

MIDDLEWARE: list[str] = []

ROOT_URLCONF = "benchmarks.stack_press.apps.django_app.urls"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("BENCH_DB_NAME", "bench_django"),
        "USER": os.environ.get("BENCH_DB_USER", "phzyx"),
        "PASSWORD": os.environ.get("BENCH_DB_PASSWORD", "phzyx"),
        "HOST": os.environ.get("BENCH_DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("BENCH_DB_PORT", "5518"),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
