from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


def status_for_dates(start_date, end_date):
    today = timezone.localdate()
    if end_date and end_date < today:
        return 'completed'
    if start_date and start_date <= today:
        return 'in_progress'
    return 'upcoming'


def link_and_create_affectations(apps, schema_editor):
    AffectationStage = apps.get_model('appstage', 'AffectationStage')
    Candidature = apps.get_model('appstage', 'Candidature')

    linked_candidature_ids = set()
    for affectation in AffectationStage.objects.select_related('offre_stage').iterator():
        candidature = Candidature.objects.filter(
            student_id=affectation.student_id,
            offre_stage_id=affectation.offre_stage_id,
            status='accepted',
        ).exclude(pk__in=linked_candidature_ids).order_by('created_at').first()

        affectation.start_date = affectation.offre_stage.start_date
        affectation.end_date = affectation.offre_stage.end_date
        affectation.status = status_for_dates(affectation.start_date, affectation.end_date)
        update_fields = ['start_date', 'end_date', 'status']
        if candidature:
            affectation.candidature_id = candidature.pk
            linked_candidature_ids.add(candidature.pk)
            update_fields.append('candidature')
        affectation.save(update_fields=update_fields)

    accepted = Candidature.objects.filter(status='accepted').select_related('offre_stage')
    for candidature in accepted.iterator():
        if AffectationStage.objects.filter(candidature_id=candidature.pk).exists():
            continue
        offer = candidature.offre_stage
        AffectationStage.objects.create(
            candidature_id=candidature.pk,
            student_id=candidature.student_id,
            offre_stage_id=candidature.offre_stage_id,
            start_date=offer.start_date,
            end_date=offer.end_date,
            status=status_for_dates(offer.start_date, offer.end_date),
        )


class Migration(migrations.Migration):

    dependencies = [
        ('appstage', '0017_candidature_decision_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='affectationstage',
            name='candidature',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='affectation',
                to='appstage.candidature',
            ),
        ),
        migrations.AddField(
            model_name='affectationstage',
            name='end_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='affectationstage',
            name='objectives',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='affectationstage',
            name='start_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='affectationstage',
            name='status',
            field=models.CharField(
                choices=[
                    ('upcoming', 'À venir'),
                    ('in_progress', 'En cours'),
                    ('completed', 'Terminé'),
                    ('cancelled', 'Interrompu'),
                ],
                default='upcoming',
                max_length=20,
            ),
        ),
        migrations.RunPython(link_and_create_affectations, migrations.RunPython.noop),
    ]
