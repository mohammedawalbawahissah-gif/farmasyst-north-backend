from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0003_order_payment_reference'),
    ]

    operations = [
        migrations.AlterField(
            model_name='produce',
            name='accepts_card',
            field=models.BooleanField(default=False, help_text='Accept Card via Hubtel'),
        ),
        migrations.AlterField(
            model_name='order',
            name='payment_method',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('momo',             'MTN Mobile Money'),
                    ('card',             'Card (Hubtel)'),
                    ('bank_transfer',    'Bank Transfer'),
                    ('cash_on_delivery', 'Cash on Delivery'),
                ],
                default='cash_on_delivery',
            ),
        ),
    ]
