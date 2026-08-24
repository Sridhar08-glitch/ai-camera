from django.apps import AppConfig


class ProcessingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.processing"
    label = "processing"

    def ready(self):
        # Register processing metrics in the observability allowlist at import time.
        from apps.processing import observability  # noqa: F401

        # Register the detection-metadata retention handler (Phase 6 §38).
        # Imports models lazily inside its methods — no import cycle at ready().
        from apps.processing import retention_handlers  # noqa: F401
