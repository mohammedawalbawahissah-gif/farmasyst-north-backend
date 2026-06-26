from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_otpverification_alter_user_role'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='language',
            field=models.CharField(
                choices=[
                    ('en',  'English'),
                    ('dag', 'Dagbani'),
                    ('tw',  'Twi (Akan)'),
                    ('ee',  'Ewe'),
                    ('fat', 'Fante'),
                    ('gaa', 'Ga'),
                    ('hau', 'Hausa'),
                    ('kus', 'Kusaal'),
                    ('nzi', 'Nzema'),
                    ('gur', 'Gurene (Frafra)'),
                    ('kas', 'Kasem'),
                    ('bim', 'Bimoba'),
                    ('kon', 'Konkomba'),
                    ('mam', 'Mampruli'),
                ],
                default='en',
                max_length=10,
            ),
        ),
    ]
