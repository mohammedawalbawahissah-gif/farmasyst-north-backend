import uuid
import django.db.models.deletion
import accounts.otp_models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='OTPVerification',
            fields=[
                ('id',         models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('channel',    models.CharField(max_length=10, choices=[('sms', 'SMS'), ('email', 'Email')])),
                ('code',       models.CharField(max_length=6, default=accounts.otp_models._generate_otp)),
                ('is_used',    models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('user',       models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='otp_verifications',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'otp_verifications', 'ordering': ['-created_at']},
        ),
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[
                    ('farmer',             'Farmer'),
                    ('investor',           'Investor'),
                    ('consumer',           'Consumer'),
                    ('monitoring_officer', 'Monitoring Officer'),
                    ('admin',              'Admin'),
                    ('vet',                'Veterinarian'),
                    ('input_dealer',       'Input Dealer'),
                ],
                default='farmer',
                max_length=20,
            ),
        ),
    ]
