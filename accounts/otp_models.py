import uuid
import secrets
from django.db import models
from django.utils import timezone
from datetime import timedelta
from accounts.models import User


def _generate_otp():
    # secrets.randbelow is a CSPRNG (unlike the `random` module, which is a
    # predictable Mersenne Twister and unsuitable for anything security-related).
    return f'{secrets.randbelow(1_000_000):06d}'


class OTPVerification(models.Model):
    """
    Stores a one-time 6-digit code for phone or email verification.
    Expires after 10 minutes. Can be used once only.
    """
    class Channel(models.TextChoices):
        SMS   = 'sms',   'SMS'
        EMAIL = 'email', 'Email'

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otp_verifications')
    channel    = models.CharField(max_length=10, choices=Channel.choices)
    code       = models.CharField(max_length=6, default=_generate_otp)
    is_used    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = 'otp_verifications'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=10)
        super().save(*args, **kwargs)

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at

    def __str__(self):
        return f'{self.channel} OTP for {self.user.email} [{"used" if self.is_used else "active"}]'
