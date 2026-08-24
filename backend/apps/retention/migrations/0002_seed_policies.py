"""Seed default retention policies for the data categories that exist in Phase 2."""
from django.db import migrations


def seed(apps, schema_editor):
    RetentionPolicy = apps.get_model("retention", "RetentionPolicy")
    from apps.common.datacategories import DataCategory

    defaults = [
        # category, days, enabled, dry_run_default
        (DataCategory.SECURITY_AUDIT, 365, False, True),   # must be deliberately enabled
        (DataCategory.SYSTEM_METRIC, 30, True, False),     # low-risk automatic cleanup
    ]
    for category, days, enabled, dry in defaults:
        RetentionPolicy.objects.update_or_create(
            category=category,
            defaults={
                "retention_days": days,
                "enabled": enabled,
                "dry_run_default": dry,
                "batch_size": 1000,
                "max_deletes_per_run": 100000,
            },
        )


def unseed(apps, schema_editor):
    RetentionPolicy = apps.get_model("retention", "RetentionPolicy")
    from apps.common.datacategories import DataCategory

    RetentionPolicy.objects.filter(
        category__in=[DataCategory.SECURITY_AUDIT, DataCategory.SYSTEM_METRIC]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("retention", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
