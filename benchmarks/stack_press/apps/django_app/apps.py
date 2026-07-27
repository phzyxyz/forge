from django.apps import AppConfig


class DjangoAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "benchmarks.stack_press.apps.django_app"
    label = "stack_press_django"
