from rest_framework import serializers
from accounts.serializers import UserSerializer
from .models import InputDealerProfile, FarmInput


class InputDealerProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = InputDealerProfile
        fields = '__all__'
        read_only_fields = ['id', 'user', 'approval_status', 'approved_by', 'created_at', 'updated_at']


class FarmInputSerializer(serializers.ModelSerializer):
    dealer_name   = serializers.ReadOnlyField()
    business_name = serializers.ReadOnlyField()
    dealer_phone  = serializers.SerializerMethodField()
    photo         = serializers.SerializerMethodField()

    def get_dealer_phone(self, obj):
        try:
            return obj.dealer.dealer_profile.phone or ''
        except Exception:
            return ''

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
        model = FarmInput
        fields = '__all__'
        read_only_fields = ['id', 'dealer', 'created_at', 'updated_at']
