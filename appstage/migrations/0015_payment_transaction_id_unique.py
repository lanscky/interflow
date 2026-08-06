from django.db import migrations, models


def remove_duplicate_transactions(apps, schema_editor):
    Payment = apps.get_model("appstage", "Payment")
    seen = set()
    for payment in Payment.objects.order_by("id").iterator():
        if payment.transaction_id in seen:
            payment.delete()
        else:
            seen.add(payment.transaction_id)


class Migration(migrations.Migration):
    dependencies = [("appstage", "0014_config")]

    operations = [
        migrations.RunPython(remove_duplicate_transactions, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="payment",
            name="transaction_id",
            field=models.CharField(max_length=255, unique=True),
        ),
    ]
