from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('credit', '0002_creditapplication_matched_investor'),
    ]

    operations = [
        migrations.AlterField(
            model_name='creditapplication',
            name='status',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('draft',        'Draft'),
                    ('submitted',    'Submitted'),
                    ('under_review', 'Under Review'),
                    ('scored',       'Scored'),
                    ('matched',      'Matched to Investor'),
                    ('approved',     'Approved'),
                    ('agreement',    'Agreement Pending'),
                    ('disbursed',    'Disbursed'),
                    ('rejected',     'Rejected'),
                    ('withdrawn',    'Withdrawn'),
                ],
                default='draft',
            ),
        ),
    ]
