import json
from pathlib import Path

from django.db import migrations


def normalize(value):
    return " ".join(str(value or "").casefold().split())


def seed_schools(apps, schema_editor):
    School = apps.get_model("appstage", "School")
    catalogue_path = Path(__file__).resolve().parents[1] / "data" / "rdc_schools.json"
    rows = json.loads(catalogue_path.read_text(encoding="utf-8"))
    existing = list(School.objects.all())
    by_registry_id = {school.registry_id: school for school in existing if school.registry_id}
    by_identity = {
        (normalize(school.name), normalize(school.province), normalize(school.territory)): school
        for school in existing
    }
    fields = (
        "name", "sigle", "category", "ownership", "territory", "province",
        "approval_status", "source_url", "is_active",
    )
    to_create = []
    to_update = []

    for row in rows:
        identity = (normalize(row["name"]), normalize(row["province"]), normalize(row["territory"]))
        school = by_registry_id.get(row["registry_id"]) or by_identity.get(identity)
        if school is None:
            to_create.append(School(registry_id=row["registry_id"], **{field: row.get(field, "") for field in fields}))
            continue
        school.registry_id = row["registry_id"]
        for field in fields:
            setattr(school, field, row.get(field, ""))
        to_update.append(school)

    School.objects.bulk_create(to_create, batch_size=250)
    if to_update:
        School.objects.bulk_update(to_update, ("registry_id", *fields), batch_size=250)


class Migration(migrations.Migration):
    dependencies = [("appstage", "0026_alter_school_options_school_approval_status_and_more")]
    operations = [migrations.RunPython(seed_schools, migrations.RunPython.noop)]
