from django.apps import AppConfig


class RetentionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.retention"
    label = "retention"

    def ready(self):
        # Register built-in handlers for categories that have real data.
        from apps.retention import handlers  # noqa: F401
