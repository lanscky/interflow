from django.db import migrations, models
from django.utils import timezone
from datetime import timedelta


def backfill_recent_decisions(apps, schema_editor):
    Candidature = apps.get_model('appstage', 'Candidature')
    AffectationStage = apps.get_model('appstage', 'AffectationStage')
    Notification = apps.get_model('appstage', 'Notification')
    recent = Candidature.objects.filter(
        status__in=['accepted', 'rejected'],
        reviewed_at__gte=timezone.now() - timedelta(days=30),
    ).select_related('student__user', 'offre_stage__company')
    for candidature in recent.iterator():
        accepted = candidature.status == 'accepted'
        affectation_id = AffectationStage.objects.filter(
            candidature_id=candidature.id,
        ).values_list('id', flat=True).first() if accepted else None
        Notification.objects.get_or_create(
            unique_key=f"application-decision:{candidature.id}:{candidature.status}",
            defaults={
                'recipient_id': candidature.student.user_id,
                'notification_type': 'application_decision',
                'title': 'Candidature acceptée' if accepted else 'Candidature non retenue',
                'message': (
                    f"{candidature.offre_stage.company.name} a accepté votre candidature pour « {candidature.offre_stage.title} »."
                    if accepted else
                    f"{candidature.offre_stage.company.name} a répondu à votre candidature pour « {candidature.offre_stage.title} »."
                ),
                'data': {
                    'application_id': candidature.id,
                    'offer_id': candidature.offre_stage_id,
                    'stage_id': affectation_id,
                    'status': candidature.status,
                },
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('appstage', '0021_notification'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='notification_type',
            field=models.CharField(
                choices=[
                    ('application_decision', 'Décision de candidature'),
                    ('report_submitted', 'Rapport soumis'),
                    ('report_validated', 'Rapport validé'),
                    ('evaluation_published', 'Évaluation publiée'),
                    ('weekly_reminder', 'Rappel hebdomadaire'),
                ],
                max_length=40,
            ),
        ),
        migrations.RunPython(backfill_recent_decisions, migrations.RunPython.noop),
    ]
