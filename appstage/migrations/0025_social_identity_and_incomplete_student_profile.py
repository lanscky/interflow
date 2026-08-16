from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('appstage', '0024_pushdevice'),
    ]

    operations = [
        migrations.AlterField(
            model_name='student',
            name='filiere',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AlterField(
            model_name='student',
            name='niveau',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.CreateModel(
            name='SocialIdentity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(choices=[('google', 'Google')], max_length=20)),
                ('provider_user_id', models.CharField(max_length=255)),
                ('email_at_link', models.EmailField(blank=True, default='', max_length=254)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='social_identities', to='appstage.user')),
            ],
        ),
        migrations.AddConstraint(
            model_name='socialidentity',
            constraint=models.UniqueConstraint(fields=('provider', 'provider_user_id'), name='unique_social_provider_identity'),
        ),
        migrations.AddConstraint(
            model_name='socialidentity',
            constraint=models.UniqueConstraint(fields=('user', 'provider'), name='unique_social_provider_per_user'),
        ),
    ]
