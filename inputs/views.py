from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import InputDealerProfile, FarmInput
from .serializers import InputDealerProfileSerializer, FarmInputSerializer
from accounts.permissions import IsAdmin, IsInputDealer


class InputDealerProfileViewSet(viewsets.ModelViewSet):
    serializer_class = InputDealerProfileSerializer
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['approval_status', 'region']
    search_fields    = ['business_name', 'user__first_name', 'user__last_name']

    def get_queryset(self):
        return InputDealerProfile.objects.select_related('user').all()

    def get_permissions(self):
        if self.action in ('approve', 'suspend', 'destroy'):
            return [IsAdmin()]
        if self.action in ('update', 'partial_update'):
            return [IsInputDealer()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get', 'patch'], permission_classes=[IsInputDealer])
    def me(self, request):
        profile, _ = InputDealerProfile.objects.get_or_create(
            user=request.user,
            defaults={'business_name': ''},
        )
        if request.method == 'PATCH':
            serializer = InputDealerProfileSerializer(profile, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        return Response(InputDealerProfileSerializer(profile).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def approve(self, request, pk=None):
        profile = self.get_object()
        profile.approval_status = 'approved'
        profile.approved_by = request.user
        profile.save()
        profile.user.is_active = True
        profile.user.is_verified = True
        profile.user.save()
        return Response(InputDealerProfileSerializer(profile).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def suspend(self, request, pk=None):
        profile = self.get_object()
        profile.approval_status = 'suspended'
        profile.save()
        return Response(InputDealerProfileSerializer(profile).data)


class FarmInputViewSet(viewsets.ModelViewSet):
    serializer_class = FarmInputSerializer
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['input_type', 'is_available', 'region']
    search_fields    = ['name', 'brand', 'description']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'input_dealer':
            return FarmInput.objects.filter(dealer=user)
        return FarmInput.objects.filter(is_available=True)

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsInputDealer()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(dealer=self.request.user)

    @action(detail=False, methods=['get'], permission_classes=[IsInputDealer])
    def my_listings(self, request):
        qs = FarmInput.objects.filter(dealer=request.user)
        return Response(FarmInputSerializer(qs, many=True).data)
