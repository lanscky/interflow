from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('appstage', '0018_affectationstage_lifecycle'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='StageWeeklyReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('week_start', models.DateField()),
                ('activities', models.TextField()),
                ('learnings', models.TextField(blank=True, default='')),
                ('difficulties', models.TextField(blank=True, default='')),
                ('status', models.CharField(choices=[('draft', 'Brouillon'), ('submitted', 'Soumis'), ('validated', 'Validé')], default='draft', max_length=20)),
                ('company_comment', models.TextField(blank=True, default='')),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('validated_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('affectation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='weekly_reports', to='appstage.affectationstage')),
                ('validated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='validated_stage_reports', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-week_start', '-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='stageweeklyreport',
            constraint=models.UniqueConstraint(fields=('affectation', 'week_start'), name='unique_stage_report_per_week'),
        ),
    ]
