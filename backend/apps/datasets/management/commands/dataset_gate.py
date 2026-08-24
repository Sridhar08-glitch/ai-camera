"""
Dataset gate / status CLI (Phase 6T-A). Reports production-training eligibility for
dataset versions — the same code path the training runtime enforces. Read-only.

    python manage.py dataset_gate            # list all versions + eligibility
    python manage.py dataset_gate --eligible # list only production-eligible ids
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.datasets.gate import check_version_eligible
from apps.datasets.models import DatasetVersion


class Command(BaseCommand):
    help = "Report dataset-version production-training eligibility (gate view)."

    def add_arguments(self, parser):
        parser.add_argument("--eligible", action="store_true",
                            help="only list production-eligible version ids")

    def handle(self, *args, **opts):
        versions = DatasetVersion.objects.select_related("dataset").all()
        if not versions:
            self.stdout.write("no dataset versions registered")
            return
        for v in versions:
            res = check_version_eligible(v)
            if opts["eligible"]:
                if res.eligible:
                    self.stdout.write(str(v.id))
                continue
            mark = "ELIGIBLE" if res.eligible else "BLOCKED"
            reasons = "" if res.eligible else f" — {'; '.join(res.reasons)}"
            self.stdout.write(f"[{mark}] {v.dataset.name}:{v.version} "
                              f"({v.rights_status}/{v.approval_status}){reasons}")
