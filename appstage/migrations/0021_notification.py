from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('appstage', '0020_stagecertificate'),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(choices=[('report_submitted', 'Rapport soumis'), ('report_validated', 'Rapport validé'), ('evaluation_published', 'Évaluation publiée'), ('weekly_reminder', 'Rappel hebdomadaire')], max_length=40)),
                ('title', models.CharField(max_length=180)),
                ('message', models.TextField()),
                ('data', models.JSONField(blank=True, default=dict)),
                ('unique_key', models.CharField(blank=True, max_length=180, null=True, unique=True)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='appstage.user')),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
