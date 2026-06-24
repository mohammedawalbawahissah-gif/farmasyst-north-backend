from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0003_alter_user_language'),
    ]

    operations = [
        migrations.CreateModel(
            name='AIChatSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ai_sessions', to='accounts.user')),
            ],
            options={'db_table': 'ai_chat_sessions', 'ordering': ['-updated_at']},
        ),
        migrations.CreateModel(
            name='AIChatMessage',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('role', models.CharField(choices=[('user', 'User'), ('assistant', 'Assistant')], max_length=10)),
                ('content', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='ai.aichatsession')),
            ],
            options={'db_table': 'ai_chat_messages', 'ordering': ['created_at']},
        ),
    ]
