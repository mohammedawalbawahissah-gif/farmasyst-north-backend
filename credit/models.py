import uuid
from django.db import models
from accounts.models import User
from farms.models import Farm


class CreditApplication(models.Model):
    class CreditType(models.TextChoices):
        FUNDING  = 'funding',  'Funding'
        INPUTS   = 'inputs',   'Farm Inputs'
        TRAINING = 'training', 'Training Enrolment'

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
