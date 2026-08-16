from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def migrate_decision_messages(apps, schema_editor):
    Candidature = apps.get_model('appstage', 'Candidature')
    Evaluation = apps.get_model('appstage', 'Evaluation')

    evaluations = Evaluation.objects.filter(
        candidature__status__in=['accepted', 'rejected'],
        candidature__company_message='',
    ).select_related('candidature')

    disposable_evaluation_ids = []
    for evaluation in evaluations.iterator():
        candidature = evaluation.candidature
        candidature.company_message = evaluation.comments
        candidature.reviewed_at = evaluation.created_at
        candidature.save(update_fields=['company_message', 'reviewed_at'])
        if evaluation.score == 0:
            disposable_evaluation_ids.append(evaluation.pk)

    # L'ancien portail créait une fausse évaluation avec score 0 uniquement
    # pour stocker le message de décision. Le message ayant été préservé sur
    # la candidature, ces enregistrements ne sont pas des évaluations finales.
    Evaluation.objects.filter(pk__in=disposable_evaluation_ids).delete()


def restore_legacy_decision_evaluations(apps, schema_editor):
    Candidature = apps.get_model('appstage', 'Candidature')
    Evaluation = apps.get_model('appstage', 'Evaluation')

    candidatures = Candidature.objects.filter(
        status__in=['accepted', 'rejected'],
    ).exclude(company_message='')
    for candidature in candidatures.iterator():
        Evaluation.objects.get_or_create(
            candidature=candidature,
            defaults={'score': 0, 'comments': candidature.company_message},
        )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('appstage', '0016_company_logo'),
    ]

    operations = [
        migrations.AddField(
            model_name='candidature',
            name='company_message',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='candidature',
            name='reviewed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='candidature',
            name='reviewed_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reviewed_candidatures',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(migrate_decision_messages, restore_legacy_decision_evaluations),
    ]
