from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('farms', '0003_farmactivitylog_local_cock_count_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='farmactivitylog',
            name='media_file',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to='farms/activity_media/',
                help_text='Photo or video of today\'s farm activity',
            ),
        ),
        migrations.AddField(
            model_name='farmactivitylog',
            name='media_type',
            field=models.CharField(
                max_length=10,
                blank=True,
                choices=[('image', 'Image'), ('video', 'Video')],
                default='',
                help_text='Type of uploaded media',
            ),
        ),
        migrations.AddField(
            model_name='farmactivitylog',
            name='media_captured_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text='Timestamp when the media was captured (auto-set or device-provided)',
            ),
        ),
    ]
