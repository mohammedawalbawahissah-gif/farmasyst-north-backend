from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_alter_user_language'),
        ('credit', '0003_add_agreement_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectApplication',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('reference', models.CharField(blank=True, max_length=20, unique=True)),
                ('project_name', models.CharField(max_length=255)),
                ('organisation', models.CharField(help_text='Name of the applying organisation', max_length=255)),
                ('credit_type', models.CharField(choices=[('funding', 'Funding'), ('inputs', 'Farm Inputs'), ('training', 'Training Enrolment')], max_length=20)),
                ('total_amount_requested', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ('repayment_period_months', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('purpose', models.TextField()),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('submitted', 'Submitted'), ('under_review', 'Under Review'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('disbursed', 'Disbursed'), ('withdrawn', 'Withdrawn')], default='draft', max_length=20)),
                ('reviewer_notes', models.TextField(blank=True)),
                ('rejection_reason', models.TextField(blank=True)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('submitted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='submitted_projects', to='accounts.user')),
                ('reviewer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_projects', to='accounts.user')),
            ],
            options={'db_table': 'project_applications', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='ProjectFarmerEntry',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('full_name', models.CharField(max_length=200)),
                ('phone', models.CharField(blank=True, max_length=20)),
                ('ghana_card_number', models.CharField(blank=True, max_length=50)),
                ('district', models.CharField(blank=True, max_length=100)),
                ('region', models.CharField(blank=True, max_length=100)),
                ('community', models.CharField(blank=True, max_length=100)),
                ('farm_name', models.CharField(blank=True, max_length=200)),
                ('flock_type', models.CharField(blank=True, max_length=30)),
                ('flock_size', models.PositiveIntegerField(default=0)),
                ('farm_size_acres', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ('amount_requested', models.DecimalField(blank=True, decimal_places=2, help_text='Credit amount requested for this specific farmer', max_digits=12, null=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='farmer_entries', to='credit.projectapplication')),
                ('farmer_account', models.ForeignKey(blank=True, limit_choices_to={'role': 'farmer'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='project_entries', to='accounts.user')),
            ],
            options={'db_table': 'project_farmer_entries', 'ordering': ['full_name']},
        ),
    ]
