from rest_framework import generics, status, viewsets
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.utils import timezone
from .models import User, FarmerProfile, InvestorProfile
from .serializers import (UserSerializer, RegisterSerializer,
                          FarmerProfileSerializer, InvestorProfileSerializer,
                          ChangePasswordSerializer, ADMIN_VERIFIED_ROLES)
from .permissions import IsAdmin, IsFarmer, IsInvestor
from farmasyst_north.sms_service import notify_officer_assigned, send_otp

GATED_ROLES = ADMIN_VERIFIED_ROLES


def _issue_otp(user, channel):
    from accounts.otp_models import OTPVerification
    OTPVerification.objects.filter(user=user, channel=channel, is_used=False).update(is_used=True)
    otp = OTPVerification.objects.create(user=user, channel=channel)
    if channel == OTPVerification.Channel.SMS and user.phone:
        send_otp(user.phone, otp.code)
    elif channel == OTPVerification.Channel.EMAIL and user.email:
        from farmasyst_north.email_service import send_email_otp
        send_email_otp(user.email, user.get_full_name(), otp.code)
    return otp


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        role = user.role

        from accounts.otp_models import OTPVerification
        otp_channels = []
        if user.phone:
            _issue_otp(user, OTPVerification.Channel.SMS)
            otp_channels.append('sms')
        if user.email:
            _issue_otp(user, OTPVerification.Channel.EMAIL)
            otp_channels.append('email')

        if role in GATED_ROLES:
            from farmasyst_north.email_service import send_account_pending_email
            send_account_pending_email(user.email, user.get_full_name(), role)
            return Response({
                'requires_verification': True,
                'requires_otp': True,
                'otp_channels': otp_channels,
                'user_id': str(user.id),
                'detail': (
                    'Account created. Please verify your contact details with the OTP code sent to you. '
                    'Your account also requires admin approval before you can log in.'
                ),
            }, status=status.HTTP_201_CREATED)

        refresh = RefreshToken.for_user(user)
        return Response({
            'requires_verification': False,
            'requires_otp': True,
            'otp_channels': otp_channels,
            'user_id': str(user.id),
            'detail': 'Account created. Please verify your contact details with the OTP code sent to you.',
            'access':  str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user, context={'request': request}).data,
        }, status=status.HTTP_201_CREATED)


class VerifyOTPView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    throttle_scope = 'otp_verify'

    def post(self, request):
        from accounts.otp_models import OTPVerification
        user_id = request.data.get('user_id')
        code    = request.data.get('code', '').strip()
        channel = request.data.get('channel', 'sms')

        if not user_id or not code:
            return Response({'detail': 'user_id and code are required.'}, status=400)
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=404)
        try:
            otp = OTPVerification.objects.filter(
                user=user, channel=channel, is_used=False
            ).latest('created_at')
        except OTPVerification.DoesNotExist:
            return Response({'detail': 'No active OTP found. Please request a new one.'}, status=400)

        if not otp.is_valid():
            return Response({'detail': 'This OTP has expired. Please request a new one.'}, status=400)
        if otp.code != code:
            return Response({'detail': 'Incorrect code. Please try again.'}, status=400)

        otp.is_used = True
        otp.save()
        if not user.is_verified:
            user.is_verified = True
            user.save(update_fields=['is_verified'])

        return Response({'detail': f'{channel.upper()} verified successfully.', 'is_verified': True})


class ResendOTPView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    throttle_scope = 'otp_resend'

    def post(self, request):
        from accounts.otp_models import OTPVerification
        user_id = request.data.get('user_id')
        channel = request.data.get('channel', 'sms')
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=404)
        if channel not in (OTPVerification.Channel.SMS, OTPVerification.Channel.EMAIL):
            return Response({'detail': 'channel must be "sms" or "email".'}, status=400)
        _issue_otp(user, channel)
        return Response({'detail': f'New OTP sent via {channel.upper()}.'})


class VerifiedTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        if not self.user.is_active:
            raise AuthenticationFailed(
                'Your account is pending admin approval or has been suspended. '
                'Please contact a FarmAsyst North administrator.'
            )
        return data


class VerifiedTokenObtainPairView(TokenObtainPairView):
    serializer_class = VerifiedTokenObtainPairSerializer
    throttle_scope = 'login'


class LogoutView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh = RefreshToken(request.data['refresh'])
            refresh.blacklist()
            return Response({'detail': 'Logged out successfully.'})
        except Exception:
            return Response({'detail': 'Invalid token.'}, status=status.HTTP_400_BAD_REQUEST)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self):
        return self.request.user


class ChangePasswordView(generics.UpdateAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()
        return Response({'detail': 'Password updated successfully.'})


class FarmerProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = FarmerProfileSerializer
    permission_classes = [IsFarmer]

    def get_object(self):
        profile, _ = FarmerProfile.objects.get_or_create(user=self.request.user)
        return profile


class InvestorProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = InvestorProfileSerializer
    permission_classes = [IsInvestor]

    def get_object(self):
        profile, _ = InvestorProfile.objects.get_or_create(user=self.request.user)
        return profile


class FarmerProfileListView(generics.ListAPIView):
    serializer_class = FarmerProfileSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['user__first_name', 'user__last_name', 'district', 'community', 'region']
    filterset_fields = ['region', 'verification_status']

    def get_queryset(self):
        user = self.request.user
        for farmer in User.objects.filter(role='farmer', is_active=True):
            FarmerProfile.objects.get_or_create(user=farmer)
        if user.role == 'admin':
            return FarmerProfile.objects.select_related('user').filter(user__role='farmer', user__is_active=True)
        return FarmerProfile.objects.select_related('user').filter(
            user__role='farmer', user__is_active=True, user__is_verified=True
        )


class FarmerProfileDetailView(generics.RetrieveAPIView):
    serializer_class = FarmerProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return FarmerProfile.objects.select_related('user').all()
        return FarmerProfile.objects.select_related('user').filter(
            user__is_active=True, user__is_verified=True
        )

    def get_object(self):
        lookup = self.kwargs.get('pk') or self.kwargs.get('user_id')
        qs = self.get_queryset()
        try:
            int(str(lookup))
            obj = qs.get(pk=lookup)
        except (ValueError, TypeError):
            obj = qs.get(user__id=lookup)
        self.check_object_permissions(self.request, obj)
        return obj


class InvestorProfileListView(generics.ListAPIView):
    serializer_class = InvestorProfileSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        for user in User.objects.filter(role='investor', is_active=True):
            InvestorProfile.objects.get_or_create(user=user)
        return InvestorProfile.objects.select_related('user').filter(
            user__role='investor', user__is_active=True
        )


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['role', 'is_verified', 'is_active']
    search_fields = ['email', 'first_name', 'last_name', 'phone']

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        user = self.get_object()
        user.is_active   = True
        user.is_verified = True
        user.save()
        if user.role == 'farmer':
            profile, _ = FarmerProfile.objects.get_or_create(user=user)
            profile.verification_status = 'verified'
            profile.save()
        if user.role == 'monitoring_officer' and user.phone:
            notify_officer_assigned(user.phone, user.get_full_name(), 'FarmAsyst North')
        return Response({'detail': f'{user.get_full_name()} verified and account activated.'})

    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        user = self.get_object()
        user.is_active = False
        user.save()
        return Response({'detail': f'{user.get_full_name()} suspended.'})

    @action(detail=True, methods=['post'])
    def unsuspend(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.save()
        return Response({'detail': f'{user.get_full_name()} reactivated.'})

    @action(detail=True, methods=['post'], url_path='update_credit_score')
    def update_credit_score(self, request, pk=None):
        user = self.get_object()
        if not hasattr(user, 'farmer_profile'):
            return Response({'detail': 'This user does not have a farmer profile.'}, status=400)
        score = request.data.get('credit_score')
        try:
            score = float(score)
            if score < 0 or score > 999.99:
                raise ValueError
        except (TypeError, ValueError):
            return Response({'detail': 'Invalid credit score. Must be between 0 and 999.99.'}, status=400)
        profile = user.farmer_profile
        profile.credit_score = score
        profile.credit_score_updated_at = timezone.now()
        profile.save()
        return Response({'detail': f'Credit score updated to {score} for {user.get_full_name()}.', 'credit_score': str(score)})
