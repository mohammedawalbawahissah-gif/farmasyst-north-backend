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

    def get_dealer_phone(self, obj):
        try:
            return obj.dealer.dealer_profile.phone or ''
        except Exception:
            return ''

    class Meta:
        model = FarmInput
        fields = '__all__'
        read_only_fields = ['id', 'dealer', 'created_at', 'updated_at']
