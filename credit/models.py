import uuid
from django.db import models
from accounts.models import User
from farms.models import Farm


class CreditApplication(models.Model):
    class CreditType(models.TextChoices):
        DIRECT_FINANCING    = 'direct_financing',    'Direct Financing'
        FARM_INPUTS         = 'farm_inputs',         'Farm Inputs'
        STRUCTURED_TRAINING = 'structured_training', 'Structured Training'
        MIXED               = 'mixed',               'Mixed'

    class Status(models.TextChoices):
        DRAFT        = 'draft',        'Draft'
        SUBMITTED    = 'submitted',    'Submitted'
        UNDER_REVIEW = 'under_review', 'Under Review'
        SCORED       = 'scored',       'Scored'
        MATCHED      = 'matched',      'Matched to Investor'
        APPROVED     = 'approved',     'Approved'
        AGREEMENT    = 'agreement',    'Agreement Pending'
        DISBURSED    = 'disbursed',    'Disbursed'
        REJECTED     = 'rejected',     'Rejected'
        WITHDRAWN    = 'withdrawn',    'Withdrawn'

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference        = models.CharField(max_length=20, unique=True, blank=True)
    farmer           = models.ForeignKey(User, on_delete=models.CASCADE, related_name='credit_applications')
    farm             = models.ForeignKey(Farm, on_delete=models.SET_NULL, null=True, blank=True, related_name='credit_applications')
    credit_type      = models.CharField(max_length=20, choices=CreditType.choices)
    amount_requested = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    repayment_period_months = models.PositiveSmallIntegerField(null=True, blank=True)
    purpose          = models.TextField()
    input_details    = models.TextField(blank=True)
    status           = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    credit_score_at_submission = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    reviewer         = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_applications')
    reviewer_notes   = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    submitted_at     = models.DateTimeField(null=True, blank=True)
    reviewed_at      = models.DateTimeField(null=True, blank=True)
    matched_investor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='matched_applications')
    approved_at      = models.DateTimeField(null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'credit_applications'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.reference} — {self.farmer.get_full_name()} ({self.status})'

    def save(self, *args, **kwargs):
        if not self.reference:
            count = CreditApplication.objects.count() + 1
            self.reference = f'CA-{count:04d}'
        super().save(*args, **kwargs)


class ApplicationDocument(models.Model):
    class DocType(models.TextChoices):
        GHANA_CARD    = 'ghana_card',    'Ghana Card'
        FARM_CERT     = 'farm_cert',     'Farm Certificate'
        FARM_PHOTO    = 'farm_photo',    'Farm Photo'
        SEASON_RECORD = 'season_record', 'Season Record'
        OTHER         = 'other',         'Other'

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(CreditApplication, on_delete=models.CASCADE, related_name='documents')
    doc_type    = models.CharField(max_length=30, choices=DocType.choices)
    file        = models.FileField(upload_to='credit/documents/')
    original_name = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'application_documents'


class CreditAgreement(models.Model):
    class AgreementStatus(models.TextChoices):
        PENDING_SIGNATURE = 'pending_signature', 'Pending Signature'
        ACTIVE            = 'active',            'Active'
        COMPLETED         = 'completed',         'Completed'
        DEFAULTED         = 'defaulted',         'Defaulted'
        CANCELLED         = 'cancelled',         'Cancelled'

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference    = models.CharField(max_length=20, unique=True, blank=True)
    application  = models.OneToOneField(CreditApplication, on_delete=models.CASCADE, related_name='agreement')
    investor     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='investment_agreements')
    farmer       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='credit_agreements')
    credit_type  = models.CharField(max_length=20, choices=CreditApplication.CreditType.choices)
    amount       = models.DecimalField(max_digits=12, decimal_places=2)
    repayment_period_months = models.PositiveSmallIntegerField()
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status       = models.CharField(max_length=25, choices=AgreementStatus.choices, default=AgreementStatus.PENDING_SIGNATURE)
    contract_document = models.FileField(upload_to='contracts/', null=True, blank=True)
    farmer_signed_at   = models.DateTimeField(null=True, blank=True)
    investor_signed_at = models.DateTimeField(null=True, blank=True)
    disbursed_at       = models.DateTimeField(null=True, blank=True)
    completed_at       = models.DateTimeField(null=True, blank=True)
    start_date         = models.DateField(null=True, blank=True)
    end_date           = models.DateField(null=True, blank=True)
    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'credit_agreements'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.reference} — {self.farmer.get_full_name()} / {self.investor.get_full_name()}'

    def save(self, *args, **kwargs):
        if not self.reference:
            count = CreditAgreement.objects.count() + 1
            self.reference = f'CT-{count:04d}'
        super().save(*args, **kwargs)


# ── Project Applications (Organisation-based group credit) ───────────────────

class ProjectApplication(models.Model):
    """
    Allows an organisation (investor/NGO/aggregator) to apply for credit
    on behalf of multiple farmers under a named project.
    """
    class Status(models.TextChoices):
        DRAFT        = 'draft',        'Draft'
        SUBMITTED    = 'submitted',    'Submitted'
        UNDER_REVIEW = 'under_review', 'Under Review'
        APPROVED     = 'approved',     'Approved'
        REJECTED     = 'rejected',     'Rejected'
        DISBURSED    = 'disbursed',    'Disbursed'
        WITHDRAWN    = 'withdrawn',    'Withdrawn'

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference        = models.CharField(max_length=20, unique=True, blank=True)
    project_name     = models.CharField(max_length=255)
    organisation     = models.CharField(max_length=255, help_text='Name of the applying organisation')
    submitted_by     = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='submitted_projects',
    )
    credit_type      = models.CharField(max_length=20, choices=CreditApplication.CreditType.choices)
    total_amount_requested = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    repayment_period_months = models.PositiveSmallIntegerField(null=True, blank=True)
    purpose          = models.TextField()
    status           = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    reviewer         = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_projects',
    )
    reviewer_notes   = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    submitted_at     = models.DateTimeField(null=True, blank=True)
    reviewed_at      = models.DateTimeField(null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'project_applications'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.reference} — {self.project_name} ({self.organisation})'

    def save(self, *args, **kwargs):
        if not self.reference:
            count = ProjectApplication.objects.count() + 1
            self.reference = f'PRJ-{count:04d}'
        super().save(*args, **kwargs)


class ProjectFarmerEntry(models.Model):
    """
    Individual farmer captured under a ProjectApplication.
    Stores farmer details collected during the organisation's application.
    If the farmer already has a platform account, link to it.
    """
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project         = models.ForeignKey(ProjectApplication, on_delete=models.CASCADE, related_name='farmer_entries')
    # Link to existing platform user if available
    farmer_account  = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='project_entries',
        limit_choices_to={'role': 'farmer'},
    )
    # Collected farmer details (captured even without a platform account)
    full_name       = models.CharField(max_length=200)
    phone           = models.CharField(max_length=20, blank=True)
    ghana_card_number = models.CharField(max_length=50, blank=True)
    district        = models.CharField(max_length=100, blank=True)
    region          = models.CharField(max_length=100, blank=True)
    community       = models.CharField(max_length=100, blank=True)
    farm_name       = models.CharField(max_length=200, blank=True)
    flock_type      = models.CharField(max_length=30, blank=True)
    flock_size      = models.PositiveIntegerField(default=0)
    farm_size_acres = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    amount_requested = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                            help_text='Credit amount requested for this specific farmer')
    notes           = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'project_farmer_entries'
        ordering = ['full_name']

    def __str__(self):
        return f'{self.full_name} — {self.project.reference}'
