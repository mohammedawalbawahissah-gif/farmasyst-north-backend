import uuid
from django.db import models
from accounts.models import User
from farms.models import Farm


class Produce(models.Model):
    class ProduceType(models.TextChoices):
        BROILERS       = 'broilers',       'Broilers'
        EGGS           = 'eggs',           'Eggs'
        LAYERS         = 'layers',         'Layer Birds'
        DAY_OLD        = 'day_old',        'Day-old Chicks'
        SMOKED         = 'smoked',         'Smoked Chicken'
        GUINEA_FOWL    = 'guinea_fowl',    'Guinea Fowl'
        TURKEY         = 'turkey',         'Turkey'
        DUCK           = 'duck',           'Duck'
        QUAIL          = 'quail',          'Quail'
        OTHER          = 'other',          'Other'

    class EggSize(models.TextChoices):
        SMALL  = 'small',  'Small'
        MEDIUM = 'medium', 'Medium'
        LARGE  = 'large',  'Large'
        JUMBO  = 'jumbo',  'Jumbo'

    class Unit(models.TextChoices):
        KG    = 'kg',    'Per KG'
        TRAY  = 'tray',  'Per Tray'
        BIRD  = 'bird',  'Per Bird'
        CRATE = 'crate', 'Per Crate'
        BAG   = 'bag',   'Per Bag'

    class ListingStatus(models.TextChoices):
        ACTIVE   = 'active',   'Active'
        SOLD_OUT = 'sold_out', 'Sold Out'
        PAUSED   = 'paused',   'Paused'
        REMOVED  = 'removed',  'Removed'

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    farm         = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='listings')
    seller       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='listings')
    produce_type = models.CharField(max_length=20, choices=ProduceType.choices)
    name         = models.CharField(max_length=200)
    description  = models.TextField(blank=True)
    price        = models.DecimalField(max_digits=10, decimal_places=2)
    unit         = models.CharField(max_length=10, choices=Unit.choices)
    quantity_available = models.DecimalField(max_digits=10, decimal_places=2)
    min_order    = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    egg_size     = models.CharField(max_length=10, choices=EggSize.choices, null=True, blank=True,
                       help_text='Only applicable when produce_type is eggs')
    photo        = models.ImageField(upload_to='marketplace/produce/', null=True, blank=True)
    status       = models.CharField(max_length=20, choices=ListingStatus.choices, default=ListingStatus.ACTIVE)
    # Seller contact & payment preferences
    contact_phone       = models.CharField(max_length=20, blank=True, help_text='Phone number buyers can reach the seller on')
    accepts_momo        = models.BooleanField(default=True,  help_text='Accept MTN Mobile Money')
    accepts_card        = models.BooleanField(default=False, help_text='Accept Card via Paystack')
    accepts_bank_transfer = models.BooleanField(default=False, help_text='Accept Bank Transfer')
    accepts_cod         = models.BooleanField(default=True,  help_text='Accept Cash on Delivery')

    is_organic   = models.BooleanField(default=False)
    avg_rating   = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_orders = models.PositiveIntegerField(default=0)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'produce_listings'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} — {self.farm.name}'


class Order(models.Model):
    class OrderStatus(models.TextChoices):
        PENDING    = 'pending',    'Pending'
        CONFIRMED  = 'confirmed',  'Confirmed'
        PROCESSING = 'processing', 'Processing'
        SHIPPED    = 'shipped',    'Shipped'
        DELIVERED  = 'delivered',  'Delivered'
        CANCELLED  = 'cancelled',  'Cancelled'
        REFUNDED   = 'refunded',   'Refunded'

    class DeliveryType(models.TextChoices):
        PICKUP   = 'pickup',   'Farm Pickup'
        DELIVERY = 'delivery', 'Home Delivery'

    class PaymentMethod(models.TextChoices):
        MOMO             = 'momo',             'MTN Mobile Money'
        CARD             = 'card',             'Card (Paystack)'
        BANK_TRANSFER    = 'bank_transfer',    'Bank Transfer'
        CASH_ON_DELIVERY = 'cash_on_delivery', 'Cash on Delivery'

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference     = models.CharField(max_length=20, unique=True, blank=True)
    buyer         = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    status        = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    delivery_type = models.CharField(max_length=20, choices=DeliveryType.choices, default=DeliveryType.PICKUP)
    delivery_address = models.TextField(blank=True)
    delivery_date = models.DateField(null=True, blank=True)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH_ON_DELIVERY)
    total_amount  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes             = models.TextField(blank=True)
    payment_reference = models.CharField(max_length=100, blank=True, default='')
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'orders'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.reference:
            count = Order.objects.count() + 1
            self.reference = f'ORD-{count:05d}'
        super().save(*args, **kwargs)


class OrderItem(models.Model):
    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order     = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    produce   = models.ForeignKey(Produce, on_delete=models.CASCADE)
    quantity  = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal  = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = 'order_items'


class ProduceReview(models.Model):
    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    produce   = models.ForeignKey(Produce, on_delete=models.CASCADE, related_name='reviews')
    reviewer  = models.ForeignKey(User, on_delete=models.CASCADE)
    rating    = models.PositiveSmallIntegerField()  # 1-5
    comment   = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'produce_reviews'
        unique_together = [('produce', 'reviewer')]
