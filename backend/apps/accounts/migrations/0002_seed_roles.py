"""Seed the fixed platform roles (Phase 1 §11)."""
from django.db import migrations


def seed_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    from apps.common.roles import ROLE_DEFINITIONS, RoleCode

    labels = dict(RoleCode.choices)
    for code, description in ROLE_DEFINITIONS.items():
        Role.objects.update_or_create(
            code=code,
            defaults={"name": labels[code], "description": description},
        )


def unseed_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    from apps.common.roles import ROLE_DEFINITIONS

    Role.objects.filter(code__in=list(ROLE_DEFINITIONS)).delete()


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunPython(seed_roles, unseed_roles)]
