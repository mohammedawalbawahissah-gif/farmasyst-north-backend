import uuid
from django.db import models
from accounts.models import User


class AIChatSession(models.Model):
    """Stores AI assistant chat history per user session."""
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_sessions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ai_chat_sessions'
        ordering = ['-updated_at']

    def __str__(self):
        return f'Session {self.id} — {self.user.get_full_name()}'


class AIChatMessage(models.Model):
    class Role(models.TextChoices):
        USER      = 'user',      'User'
        ASSISTANT = 'assistant', 'Assistant'

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session    = models.ForeignKey(AIChatSession, on_delete=models.CASCADE, related_name='messages')
    role       = models.CharField(max_length=10, choices=Role.choices)
    content    = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ai_chat_messages'
        ordering = ['created_at']
