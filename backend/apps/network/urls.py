"""Network routes under /api/v1/network/ (flat, filter-based)."""
from rest_framework.routers import DefaultRouter

from apps.network import views

router = DefaultRouter(trailing_slash=False)
router.register("cities", views.CityViewSet, basename="city")
router.register("zones", views.ZoneViewSet, basename="zone")
router.register("roads", views.RoadViewSet, basename="road")
router.register("road-segments", views.RoadSegmentViewSet, basename="road-segment")
router.register("intersections", views.IntersectionViewSet, basename="intersection")
router.register("approaches", views.ApproachViewSet, basename="approach")
router.register("lanes", views.LaneViewSet, basename="lane")
router.register("cameras", views.CameraViewSet, basename="camera")
router.register("camera-coverages", views.CameraLaneCoverageViewSet, basename="camera-coverage")
router.register("regions-of-interest", views.RegionOfInterestViewSet, basename="roi")
router.register("counting-lines", views.CountingLineViewSet, basename="counting-line")
router.register("stop-lines", views.StopLineViewSet, basename="stop-line")

urlpatterns = router.urls
