"""Seed default retention policies for video data categories (disabled by default)."""
from django.db import migrations


def seed(apps, schema_editor):
    RetentionPolicy = apps.get_model("retention", "RetentionPolicy")
    from apps.common.datacategories import DataCategory

    defaults = [
        # category, days, enabled, dry_run_default
        (DataCategory.RAW_VIDEO, 365, False, True),        # long, deliberately enabled by an admin
        (DataCategory.VIDEO_THUMBNAIL, 365, False, True),  # orphaned thumbnails only
    ]
    for category, days, enabled, dry in defaults:
        RetentionPolicy.objects.update_or_create(
            category=category,
            defaults={
                "retention_days": days,
                "enabled": enabled,
                "dry_run_default": dry,
                "batch_size": 100,
                "max_deletes_per_run": 10000,
            },
        )


def unseed(apps, schema_editor):
    RetentionPolicy = apps.get_model("retention", "RetentionPolicy")
    from apps.common.datacategories import DataCategory

    RetentionPolicy.objects.filter(
        category__in=[DataCategory.RAW_VIDEO, DataCategory.VIDEO_THUMBNAIL]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("ingestion", "0001_initial"),
        ("retention", "0002_seed_policies"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
