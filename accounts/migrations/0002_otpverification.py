from django.db import migrations, models
import django.db.models.deletion
import uuid
import accounts.otp_models


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
                ('user',       models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                               related_name='otp_verifications', to='accounts.user')),
            ],
            options={'db_table': 'otp_verifications', 'ordering': ['-created_at']},
        ),
    ]
