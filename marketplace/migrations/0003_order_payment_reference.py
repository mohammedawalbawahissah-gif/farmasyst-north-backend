from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0002_order_payment_method_produce_accepts_bank_transfer_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='payment_reference',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]
