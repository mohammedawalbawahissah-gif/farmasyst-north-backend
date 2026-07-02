from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from .models import VetProfile, VetService, VetBooking
from .serializers import VetProfileSerializer, VetServiceSerializer, VetBookingSerializer
from accounts.permissions import IsAdmin, IsVet, IsFarmer


class VetProfileViewSet(viewsets.ModelViewSet):
    serializer_class = VetProfileSerializer
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['approval_status', 'region', 'is_available']
    search_fields    = ['clinic_name', 'specialisation', 'user__first_name', 'user__last_name']

    def get_queryset(self):
        return VetProfile.objects.select_related('user').all()

    def get_permissions(self):
        if self.action in ('approve', 'suspend', 'destroy'):
            return [IsAdmin()]
        if self.action in ('update', 'partial_update'):
            return [IsVet()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get', 'patch'], permission_classes=[IsVet])
    def me(self, request):
        profile, _ = VetProfile.objects.get_or_create(
            user=request.user,
            defaults={'license_number': f'TMP-{request.user.id}', 'clinic_name': ''},
        )
        if request.method == 'PATCH':
            serializer = VetProfileSerializer(profile, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        return Response(VetProfileSerializer(profile).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def approve(self, request, pk=None):
        profile = self.get_object()
        profile.approval_status = 'approved'
        profile.approved_by = request.user
        profile.save()
        # Activate the user account so they can log in
        profile.user.is_active = True
        profile.user.is_verified = True
        profile.user.save()
        return Response(VetProfileSerializer(profile).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def suspend(self, request, pk=None):
        profile = self.get_object()
        profile.approval_status = 'suspended'
        profile.save()
        return Response(VetProfileSerializer(profile).data)


class VetServiceViewSet(viewsets.ModelViewSet):
    serializer_class = VetServiceSerializer
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['service_type', 'is_mobile', 'region', 'is_active']
    search_fields    = ['service_name', 'description']

    def get_queryset(self):
        return VetService.objects.select_related('vet').filter(is_active=True)

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsVet()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(vet=self.request.user)

    @action(detail=False, methods=['get'], permission_classes=[IsVet])
    def my_services(self, request):
        qs = VetService.objects.filter(vet=request.user)
        return Response(VetServiceSerializer(qs, many=True).data)


class VetBookingViewSet(viewsets.ModelViewSet):
    serializer_class = VetBookingSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == 'farmer':
            return VetBooking.objects.filter(farmer=user)
        if user.role == 'vet':
            return VetBooking.objects.filter(vet=user)
        if user.role == 'admin':
            return VetBooking.objects.all()
        return VetBooking.objects.none()

    def get_permissions(self):
        if self.action == 'create':
            return [IsFarmer()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        service = serializer.validated_data.get('service')
        vet = serializer.validated_data.get('vet')
        serializer.save(farmer=self.request.user, fee=service.price if service else 0)

    @action(detail=False, methods=['get'], permission_classes=[IsVet])
    def my_bookings(self, request):
        qs = VetBooking.objects.filter(vet=request.user)
        # The mobile Bookings screen has a pending/confirmed/completed tab bar
        # that relies on this filter — without it, every tab showed the same
        # unfiltered list since nothing was applying it client-side either.
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response(VetBookingSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        booking = self.get_object()
        if booking.status != 'pending':
            return Response({'detail': 'Only pending bookings can be confirmed.'}, status=400)
        booking.status = 'confirmed'
        booking.save()
        return Response(VetBookingSerializer(booking).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        booking = self.get_object()
        if booking.status != 'confirmed':
            return Response({'detail': 'Only confirmed bookings can be completed.'}, status=400)
        booking.status = 'completed'
        booking.vet_notes = request.data.get('vet_notes', '')
        booking.save()
        return Response(VetBookingSerializer(booking).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        if booking.status in ('completed',):
            return Response({'detail': 'Cannot cancel a completed booking.'}, status=400)
        booking.status = 'cancelled'
        booking.save()
        return Response(VetBookingSerializer(booking).data)
