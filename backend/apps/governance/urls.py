"""Governance routes under /api/v1/governance/."""
from rest_framework.routers import DefaultRouter

from apps.governance.views import (
    AIModelVersionViewSet,
    AIModelViewSet,
    AlgorithmDefinitionViewSet,
    AlgorithmVersionViewSet,
    ModelArtifactViewSet,
    StoredArtifactViewSet,
)

router = DefaultRouter(trailing_slash=False)
router.register("models", AIModelViewSet, basename="ai-model")
router.register("model-versions", AIModelVersionViewSet, basename="ai-model-version")
router.register("model-artifacts", ModelArtifactViewSet, basename="model-artifact")
router.register("algorithms", AlgorithmDefinitionViewSet, basename="algorithm")
router.register("algorithm-versions", AlgorithmVersionViewSet, basename="algorithm-version")
router.register("artifacts", StoredArtifactViewSet, basename="stored-artifact")

urlpatterns = router.urls
