from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('farms', '0001_initial'),
        ('marketplace', '0002_payment_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='produce',
            name='farm',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='listings',
                to='farms.farm',
            ),
        ),
    ]