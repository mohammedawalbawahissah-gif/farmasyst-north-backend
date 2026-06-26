from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User, FarmerProfile, InvestorProfile


class UserSerializer(serializers.ModelSerializer):
    full_name    = serializers.SerializerMethodField()
    credit_score = serializers.SerializerMethodField()
    # Writable — accepts file uploads on PATCH, returns absolute URL on read
    profile_photo = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ['id','email','first_name','last_name','full_name','phone','role',
                  'is_verified','is_active','profile_photo','language','date_joined','credit_score']
        read_only_fields = ['id','is_verified','is_active','date_joined','credit_score']

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_credit_score(self, obj):
        if hasattr(obj, 'farmer_profile'):
            return str(obj.farmer_profile.credit_score)
        return None

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if instance.profile_photo:
            url = instance.profile_photo.url
            # Cloudinary returns a full https:// URL already
            if url.startswith('http'):
                ret['profile_photo'] = url
            else:
                request = self.context.get('request')
                if request:
                    ret['profile_photo'] = request.build_absolute_uri(url)
                else:
                    from django.conf import settings
                    base = getattr(settings, 'BACKEND_URL', '').rstrip('/')
                    ret['profile_photo'] = f'{base}{url}' if base else url
        else:
            ret['profile_photo'] = None
        return ret


# Roles that require an admin to manually verify before the account is usable.
# All other roles (farmer, investor, consumer) are activated immediately.
ADMIN_VERIFIED_ROLES = {
    User.Role.MONITORING_OFFICER,
    User.Role.VET,
    User.Role.INPUT_DEALER,
}


class RegisterSerializer(serializers.ModelSerializer):
    password  = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email','first_name','last_name','phone','role','password','password2','language']

    def validate_role(self, value):
        if value == User.Role.ADMIN:
            raise serializers.ValidationError(
                'Admin accounts cannot be created through self-registration.'
            )
        return value

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        role = validated_data.get('role')

        requires_verification = role in ADMIN_VERIFIED_ROLES
        validated_data['is_active']   = not requires_verification
        validated_data['is_verified'] = False
        return User.objects.create_user(**validated_data)


class FarmerProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = FarmerProfile
        fields = '__all__'
        read_only_fields = ['user', 'credit_score_updated_at', 'verification_status']


class InvestorProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = InvestorProfile
        fields = '__all__'
        read_only_fields = ['user', 'is_kyc_verified']


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Old password is incorrect.')
        return value
