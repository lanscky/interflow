from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('appstage', '0015_payment_transaction_id_unique'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='logo',
            field=models.ImageField(blank=True, null=True, upload_to='company_logos/'),
        ),
    ]
