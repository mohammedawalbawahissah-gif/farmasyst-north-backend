import uuid
from django.db import models
from accounts.models import User


class Farm(models.Model):
    class FlockType(models.TextChoices):
        BROILERS            = 'broilers',            'Broilers'
        LAYERS              = 'layers',              'Layers'
        GUINEA_FOWL         = 'guinea_fowl',         'Guinea Fowl'
        TURKEY              = 'turkey',              'Turkey'
        DUCK                = 'duck',                'Duck'
        GEESE               = 'geese',               'Geese'
        OSTRICH             = 'ostrich',             'Ostrich'
        LOCAL_BIRDS         = 'local_birds',         'Local Birds (Cocks & Hens)'
        DAY_OLD_CHICKS      = 'day_old_chicks',      'Day-Old Chicks'
        HATCHERY            = 'hatchery',            'Hatchery Only'
        POULTRY_AND_HATCHERY = 'poultry_and_hatchery', 'Poultry + Hatchery'
        MEAT_PROCESSING      = 'meat_processing',    'Meat Processing Farm'
        MIXED               = 'mixed',               'Mixed Poultry'

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='farms')
    name         = models.CharField(max_length=200)
    flock_type   = models.CharField(max_length=20, choices=FlockType.choices)
    flock_size   = models.PositiveIntegerField(default=0)
    region       = models.CharField(max_length=100)
    district     = models.CharField(max_length=100)
    community    = models.CharField(max_length=100, blank=True)
    gps_address  = models.CharField(max_length=100, blank=True)
    farm_size_acres = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    has_water_source = models.BooleanField(default=False)
    has_electricity  = models.BooleanField(default=False)
    registration_cert = models.FileField(upload_to='farms/certs/', null=True, blank=True)
    farm_photo   = models.ImageField(upload_to='farms/photos/', null=True, blank=True)
    monitoring_officer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_farms',
        limit_choices_to={'role': 'monitoring_officer'},
    )
    is_active    = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'farms'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.owner.get_full_name()})'


class FarmActivityLog(models.Model):
    """Daily farm activity entries logged by the farmer."""
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    farm         = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='activity_logs')
    date         = models.DateField()

    # Split flock count by category — each defaults to 0 so existing rows stay valid
    broiler_count         = models.PositiveIntegerField(default=0)
    layer_count           = models.PositiveIntegerField(default=0)
    guinea_fowl_count     = models.PositiveIntegerField(default=0)
    turkey_count          = models.PositiveIntegerField(default=0)
    duck_count            = models.PositiveIntegerField(default=0)
    geese_count           = models.PositiveIntegerField(default=0)
    ostrich_count         = models.PositiveIntegerField(default=0)
    local_cock_count      = models.PositiveIntegerField(default=0, help_text='Local breed cocks (roosters)')
    local_hen_count       = models.PositiveIntegerField(default=0, help_text='Local breed hens')
    day_old_chick_count   = models.PositiveIntegerField(default=0)

    # Hatchery-specific fields
    eggs_in_incubation    = models.PositiveIntegerField(default=0, help_text='Number of eggs currently in incubator')
    eggs_set_today        = models.PositiveIntegerField(default=0, help_text='Eggs placed in incubator today')
    chicks_hatched        = models.PositiveIntegerField(default=0, help_text='Chicks successfully hatched today')
    hatch_rejects         = models.PositiveIntegerField(default=0, help_text='Unhatched / infertile eggs removed')
    chicks_sold           = models.PositiveIntegerField(default=0, help_text='Day-old chicks sold/dispatched today')

    # Meat processing-specific fields
    birds_received        = models.PositiveIntegerField(default=0, help_text='Live birds received for processing')
    birds_processed       = models.PositiveIntegerField(default=0, help_text='Birds processed/slaughtered today')
    carcass_weight_kg     = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Total dressed carcass weight (kg)')
    units_packaged        = models.PositiveIntegerField(default=0, help_text='Packaged units (portions, whole birds, etc.)')
    cold_storage_units    = models.PositiveIntegerField(default=0, help_text='Units moved to cold storage')

    # Keep flock_count as a computed convenience (total of all categories)
    @property
    def flock_count(self):
        return (self.broiler_count + self.layer_count + self.guinea_fowl_count +
                self.turkey_count + self.duck_count + self.geese_count +
                self.ostrich_count + self.local_cock_count + self.local_hen_count +
                self.day_old_chick_count)

    mortality    = models.PositiveIntegerField(default=0)
    feed_kg      = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    eggs_collected = models.PositiveIntegerField(default=0)
    medication_given = models.TextField(blank=True)
    notes        = models.TextField(blank=True)
    logged_by    = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'farm_activity_logs'
        ordering = ['-date']
        unique_together = [('farm', 'date')]

    def __str__(self):
        return f'{self.farm.name} — {self.date}'


class FarmAuditReport(models.Model):
    """Field verification reports submitted by FarmAsyst North agents."""
    class Outcome(models.TextChoices):
        SATISFACTORY = 'satisfactory', 'Satisfactory'
        CONCERNS     = 'concerns',     'Concerns Noted'
        UNSATISFACTORY = 'unsatisfactory', 'Unsatisfactory'

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    farm        = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='audit_reports')
    auditor     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    visit_date  = models.DateField()
    outcome     = models.CharField(max_length=20, choices=Outcome.choices)
    flock_verified = models.PositiveIntegerField()
    infrastructure_score = models.PositiveSmallIntegerField(help_text='Score out of 10')
    management_score     = models.PositiveSmallIntegerField(help_text='Score out of 10')
    biosecurity_score    = models.PositiveSmallIntegerField(help_text='Score out of 10')
    report_document = models.FileField(upload_to='audits/', null=True, blank=True)
    summary     = models.TextField()
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'farm_audit_reports'
        ordering = ['-visit_date']

    def __str__(self):
        return f'Audit: {self.farm.name} — {self.visit_date}'
