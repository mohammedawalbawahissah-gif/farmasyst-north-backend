import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra):
        extra.setdefault('role', User.Role.ADMIN)
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        FARMER             = 'farmer',             'Farmer'
        INVESTOR           = 'investor',           'Investor'
        CONSUMER           = 'consumer',           'Consumer'
        MONITORING_OFFICER = 'monitoring_officer', 'Monitoring Officer'
        ADMIN              = 'admin',              'Admin'
        VET                = 'vet',                'Veterinarian'
        INPUT_DEALER       = 'input_dealer',       'Input Dealer'

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email         = models.EmailField(unique=True)
    first_name    = models.CharField(max_length=100)
    last_name     = models.CharField(max_length=100)
    phone         = models.CharField(max_length=20, blank=True)
    role          = models.CharField(max_length=20, choices=Role.choices, default=Role.FARMER)
    is_active     = models.BooleanField(default=True)
    is_staff      = models.BooleanField(default=False)
    is_verified   = models.BooleanField(default=False)
    profile_photo = models.ImageField(upload_to='profile_photos/', null=True, blank=True)
    language      = models.CharField(max_length=10, default='en', choices=[
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
    ])
    date_joined   = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'role']

    class Meta:
        db_table = 'users'
        ordering = ['-date_joined']

    def __str__(self):
        return f'{self.get_full_name()} <{self.email}> [{self.role}]'

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()


class FarmerProfile(models.Model):
    class VerificationStatus(models.TextChoices):
        PENDING   = 'pending',   'Pending'
        SUBMITTED = 'submitted', 'Submitted'
        VERIFIED  = 'verified',  'Verified'
        REJECTED  = 'rejected',  'Rejected'

    user               = models.OneToOneField(User, on_delete=models.CASCADE, related_name='farmer_profile')
    ghana_card_number  = models.CharField(max_length=50, blank=True)
    ghana_card_photo   = models.ImageField(upload_to='kyc/ghana_cards/', null=True, blank=True)
    district           = models.CharField(max_length=100, blank=True)
    region             = models.CharField(max_length=100, blank=True)
    community          = models.CharField(max_length=100, blank=True)
    gps_address        = models.CharField(max_length=100, blank=True)
    years_of_farming   = models.PositiveSmallIntegerField(default=0)
    verification_status = models.CharField(max_length=20, choices=VerificationStatus.choices, default=VerificationStatus.PENDING)
    credit_score       = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    credit_score_updated_at = models.DateTimeField(null=True, blank=True)
    notes              = models.TextField(blank=True)
    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'farmer_profiles'

    def __str__(self):
        return f'FarmerProfile: {self.user.get_full_name()}'


class InvestorProfile(models.Model):
    class InvestorType(models.TextChoices):
        BANK        = 'bank',        'Bank / MFI'
        OFF_TAKER   = 'off_taker',   'Off-taker'
        RESTAURANT  = 'restaurant',  'Restaurant'
        AGGREGATOR  = 'aggregator',  'Aggregator'
        NGO         = 'ngo',         'NGO / Development Partner'

    user             = models.OneToOneField(User, on_delete=models.CASCADE, related_name='investor_profile')
    organisation     = models.CharField(max_length=200)
    investor_type    = models.CharField(max_length=20, choices=InvestorType.choices)
    registration_number = models.CharField(max_length=100, blank=True)
    mandate_document = models.FileField(upload_to='kyc/investor_mandates/', null=True, blank=True)
    max_investment_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    preferred_credit_types = models.JSONField(default=list)
    preferred_regions = models.JSONField(default=list)
    is_kyc_verified  = models.BooleanField(default=False)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'investor_profiles'

    def __str__(self):
        return f'{self.organisation} ({self.investor_type})'
