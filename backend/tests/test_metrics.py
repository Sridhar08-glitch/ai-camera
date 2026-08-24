"""Observability metrics tests: cardinality protection, flush, retention, API."""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.common.datacategories import DataCategory
from apps.observability import collectors
from apps.observability.models import SystemMetric
from apps.observability.tasks import flush_system_metrics
from apps.retention.models import RetentionPolicy
from apps.retention.services import execute_policy

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _reset_collectors():
    collectors.snapshot_and_reset()
    yield
    collectors.snapshot_and_reset()


def test_counter_and_summary_accumulate():
    collectors.incr("http_requests_total", {"method": "GET", "status_class": "2xx"})
    collectors.incr("http_requests_total", {"method": "GET", "status_class": "2xx"})
    collectors.observe("http_request_latency_ms", 10.0, {"method": "GET"})
    collectors.observe("http_request_latency_ms", 30.0, {"method": "GET"})
    rows = collectors.snapshot_and_reset()
    by = {(r["name"], r["labels"].get("stat")): r["value"] for r in rows}
    assert by[("http_requests_total", None)] == 2
    assert by[("http_request_latency_ms", "avg")] == 20.0
    assert by[("http_request_latency_ms", "max")] == 30.0


def test_unknown_metric_rejected():
    with pytest.raises(collectors.MetricError):
        collectors.incr("does_not_exist", {})


def test_unknown_label_rejected_cardinality_protection():
    with pytest.raises(collectors.MetricError):
        collectors.incr("http_requests_total", {"user_id": "12345"})  # not allowlisted


def test_flush_writes_aggregated_rows_and_resets():
    collectors.incr("http_requests_total", {"method": "POST", "status_class": "5xx"})
    written = flush_system_metrics()
    assert written >= 1
    assert SystemMetric.objects.filter(name="http_requests_total").exists()
    # accumulators were reset -> a second flush writes nothing
    assert flush_system_metrics() == 0


def test_metric_retention_deletes_old():
    SystemMetric.objects.create(
        name="http_requests_total", runtime="django", value=1, unit="count",
        bucket_start=timezone.now() - timedelta(days=60),
    )
    # Backdate created_at (SystemMetric is not immutable — plain update is fine).
    SystemMetric.objects.update(created_at=timezone.now() - timedelta(days=60))
    policy = RetentionPolicy.objects.get(category=DataCategory.SYSTEM_METRIC)
    policy.enabled = True
    policy.retention_days = 30
    policy.save()
    run = execute_policy(policy, dry_run=False)
    assert run.deleted == 1
    assert SystemMetric.objects.count() == 0


def test_summary_endpoint_permission(api, auth, sysadmin, operator):
    auth(api, sysadmin)
    assert api.get("/api/v1/observability/summary").status_code == 200
    auth(api, operator)
    assert api.get("/api/v1/observability/summary").status_code == 403
