from django.db import migrations, models
import django.db.models.deletion
import appstage.models


class Migration(migrations.Migration):

    dependencies = [
        ('appstage', '0019_stageweeklyreport'),
    ]

    operations = [
        migrations.CreateModel(
            name='StageCertificate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference', models.CharField(default=appstage.models.generate_certificate_reference, editable=False, max_length=24, unique=True)),
                ('issued_at', models.DateTimeField(auto_now_add=True)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('affectation', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='certificate', to='appstage.affectationstage')),
            ],
            options={'ordering': ['-issued_at']},
        ),
    ]
