from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('appstage', '0022_notification_application_decision'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='stagecertificate',
            name='affectation',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='certificates', to='appstage.affectationstage'),
        ),
        migrations.AddField(model_name='stagecertificate', name='data_hash', field=models.CharField(blank=True, default='', max_length=64)),
        migrations.AddField(model_name='stagecertificate', name='last_verified_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='stagecertificate', name='revocation_reason', field=models.TextField(blank=True, default='')),
        migrations.AddField(model_name='stagecertificate', name='verification_count', field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='stagecertificate', name='version', field=models.PositiveIntegerField(default=1)),
        migrations.AddField(
            model_name='stagecertificate',
            name='revoked_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='revoked_stage_certificates', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddConstraint(
            model_name='stagecertificate',
            constraint=models.UniqueConstraint(fields=('affectation', 'version'), name='unique_stage_certificate_version'),
        ),
    ]
