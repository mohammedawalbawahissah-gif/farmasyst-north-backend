from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from .models import User, FarmerProfile, InvestorProfile
from .serializers import (UserSerializer, RegisterSerializer,
                          FarmerProfileSerializer, InvestorProfileSerializer,
                          ChangePasswordSerializer)
from .permissions import IsAdmin, IsFarmer, IsInvestor
from farmasyst_north.sms_service import notify_officer_assigned


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            'detail': (
                'Account created successfully. Your account is pending admin verification. '
                'You will be able to log in once a FarmAsyst North administrator approves your account.'
            )
        }, status=status.HTTP_201_CREATED)


class VerifiedTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        if not user.is_active or not user.is_verified:
            raise AuthenticationFailed(
                'Your account is pending verification. '
                'Please wait for a FarmAsyst North administrator to approve your account before logging in.'
            )
        return data


class VerifiedTokenObtainPairView(TokenObtainPairView):
    serializer_class = VerifiedTokenObtainPairSerializer


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
        if user.role == 'admin':
            target_users = User.objects.filter(role='farmer', is_active=True)
        else:
            target_users = User.objects.filter(role='farmer', is_active=True, is_verified=True)

        for farmer in target_users:
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
        # SMS: notify monitoring officer if assigned
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
        from django.utils import timezone
        user = self.get_object()
        if not hasattr(user, 'farmer_profile'):
            return Response({'detail': 'This user does not have a farmer profile.'}, status=400)
        score = request.data.get('credit_score')
        try:
            score = float(score)
            if score < 0 or score > 999.99:
                raise ValueError
        except (TypeError, ValueError):
            return Response({'detail': 'Invalid credit score. Must be a number between 0 and 999.99.'}, status=400)
        profile = user.farmer_profile
        profile.credit_score = score
        profile.credit_score_updated_at = timezone.now()
        profile.save()
        return Response({'detail': f'Credit score updated to {score} for {user.get_full_name()}.', 'credit_score': str(score)})
