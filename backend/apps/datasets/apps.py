from django.apps import AppConfig


class DatasetsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.datasets"
    label = "datasets"

    def ready(self):
        # Register the dataset-manifest retention handler (Phase 6T-A).
        from apps.datasets import retention_handlers  # noqa: F401
