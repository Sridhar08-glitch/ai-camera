"""Root URL configuration."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.health.urls")),
    path("api/v1/auth/", include("apps.accounts.urls_auth")),
    path("api/v1/", include("apps.accounts.urls")),
    # Phase 2
    path("api/v1/audit/", include("apps.audit.urls")),
    path("api/v1/governance/", include("apps.governance.urls")),
    path("api/v1/retention/", include("apps.retention.urls")),
    path("api/v1/observability/", include("apps.observability.urls")),
    # Phase 3
    path("api/v1/network/", include("apps.network.urls")),
    # Phase 4
    path("api/v1/", include("apps.ingestion.urls")),
    # Phase 5
    path("api/v1/", include("apps.processing.urls")),
]
