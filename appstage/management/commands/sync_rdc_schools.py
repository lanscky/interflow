import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from appstage.models import School


CATALOGUE_PATH = Path(__file__).resolve().parents[2] / "data" / "rdc_schools.json"
SYNC_FIELDS = (
    "name",
    "sigle",
    "category",
    "ownership",
    "territory",
    "province",
    "approval_status",
    "source_url",
    "is_active",
)


def normalize(value):
    return " ".join(str(value or "").casefold().split())


def sync_catalogue(rows):
    existing = list(School.objects.all())
    by_registry_id = {school.registry_id: school for school in existing if school.registry_id}
    by_identity = {
        (normalize(school.name), normalize(school.province), normalize(school.territory)): school
        for school in existing
    }
    to_create = []
    to_update = []

    for row in rows:
        identity = (normalize(row["name"]), normalize(row["province"]), normalize(row["territory"]))
        school = by_registry_id.get(row["registry_id"]) or by_identity.get(identity)
        if school is None:
            to_create.append(School(registry_id=row["registry_id"], **{field: row.get(field, "") for field in SYNC_FIELDS}))
            continue

        school.registry_id = row["registry_id"]
        for field in SYNC_FIELDS:
            setattr(school, field, row.get(field, ""))
        to_update.append(school)

    School.objects.bulk_create(to_create, batch_size=250)
    if to_update:
        School.objects.bulk_update(to_update, ("registry_id", *SYNC_FIELDS), batch_size=250)
    return len(to_create), len(to_update)


class Command(BaseCommand):
    help = "Synchronise le catalogue des établissements ESU de la RDC depuis le snapshot officiel livré avec Totinda."

    def add_arguments(self, parser):
        parser.add_argument("--file", type=Path, default=CATALOGUE_PATH)

    @transaction.atomic
    def handle(self, *args, **options):
        path = options["file"]
        if not path.exists():
            raise CommandError(f"Catalogue introuvable : {path}")
        rows = json.loads(path.read_text(encoding="utf-8"))
        created, updated = sync_catalogue(rows)
        self.stdout.write(self.style.SUCCESS(f"Catalogue synchronisé : {created} créations, {updated} mises à jour."))
