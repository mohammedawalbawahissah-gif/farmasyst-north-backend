from rest_framework import serializers
from .models import Produce, Order, OrderItem, ProduceReview


class ProduceSerializer(serializers.ModelSerializer):
    farm_name   = serializers.CharField(source='farm.name', read_only=True)
    seller_name = serializers.CharField(source='seller.get_full_name', read_only=True)
    photo       = serializers.SerializerMethodField()

    def get_photo(self, obj):
        if not obj.photo:
            return None
        request = self.context.get('request')
        url = obj.photo.url
        if request:
            return request.build_absolute_uri(url)
        from django.conf import settings
        base = getattr(settings, 'BACKEND_URL', '').rstrip('/')
        return f'{base}{url}' if base else url

    class Meta:
        model = Produce
        fields = '__all__'
        read_only_fields = ['id', 'seller', 'avg_rating', 'total_orders', 'created_at', 'updated_at']


class OrderItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = OrderItem
        fields = ['produce', 'quantity', 'unit_price']


class OrderItemSerializer(serializers.ModelSerializer):
    produce_name = serializers.CharField(source='produce.name', read_only=True)

    class Meta:
        model  = OrderItem
        fields = ['id', 'produce', 'produce_name', 'quantity', 'unit_price', 'subtotal']


class OrderSerializer(serializers.ModelSerializer):
    items      = OrderItemSerializer(many=True, read_only=True)
    items_data = OrderItemWriteSerializer(many=True, write_only=True, source='items')
    buyer_name = serializers.CharField(source='buyer.get_full_name', read_only=True)

    class Meta:
        model  = Order
        fields = '__all__'
        read_only_fields = ['id', 'reference', 'buyer', 'total_amount', 'created_at', 'updated_at']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        order      = Order.objects.create(**validated_data)
        total      = 0
        for item in items_data:
            qty        = item['quantity']
            price      = item['unit_price']
            OrderItem.objects.create(order=order, **item)
            total += float(qty) * float(price)
        order.total_amount = total
        order.save()
        return order


class ProduceReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source='reviewer.get_full_name', read_only=True)

    class Meta:
        model = ProduceReview
        fields = '__all__'
        read_only_fields = ['id', 'reviewer', 'created_at']

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError('Rating must be between 1 and 5.')
        return value
