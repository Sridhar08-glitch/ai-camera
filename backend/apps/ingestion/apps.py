from django.apps import AppConfig


class IngestionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ingestion"
    label = "ingestion"

    def ready(self):
        from apps.ingestion import retention_handlers  # noqa: F401
