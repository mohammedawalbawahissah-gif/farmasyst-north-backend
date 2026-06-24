from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Farm, FarmActivityLog, FarmAuditReport
from .serializers import FarmSerializer, FarmActivityLogSerializer, FarmAuditReportSerializer
from accounts.permissions import (IsFarmer, IsAdmin, IsFarmerOrAdmin,
                                   IsMonitoringOfficerOrAdmin, IsMonitoringOfficer)


class FarmViewSet(viewsets.ModelViewSet):
    serializer_class = FarmSerializer
    filter_backends  = [DjangoFilterBackend]
    filterset_fields = ['flock_type', 'region', 'district', 'is_active']
    search_fields    = ['name', 'region', 'district', 'community']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'farmer':
            return Farm.objects.filter(owner=user)
        if user.role in ('admin', 'investor', 'monitoring_officer'):
            return Farm.objects.all()
        return Farm.objects.none()

    def get_permissions(self):
        if self.action in ('update', 'partial_update', 'destroy'):
            return [IsFarmer()]
        if self.action == 'create':
            return [IsFarmerOrAdmin()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == 'admin':
            owner_id = self.request.data.get('owner')
            if not owner_id:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'owner': 'This field is required when registering a farm as admin.'})
            from accounts.models import User as UserModel
            try:
                owner = UserModel.objects.get(id=owner_id, role='farmer')
            except UserModel.DoesNotExist:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'owner': 'No farmer account found with that ID.'})
            serializer.save(owner=owner)
        else:
            serializer.save(owner=user)

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin], url_path='assign_officer')
    def assign_officer(self, request, pk=None):
        """Assign or unassign a monitoring officer to/from a farm."""
        farm = self.get_object()
        officer_id = request.data.get('officer_id')
        if not officer_id:
            # Unassign
            farm.monitoring_officer = None
            farm.save(update_fields=['monitoring_officer'])
            return Response({'detail': 'Officer unassigned.', 'farm_id': str(farm.id)}, status=status.HTTP_200_OK)
        from accounts.models import User as UserModel
        try:
            officer = UserModel.objects.get(id=officer_id, role='monitoring_officer')
        except UserModel.DoesNotExist:
            return Response({'detail': 'No monitoring officer found with that ID.'}, status=status.HTTP_404_NOT_FOUND)
        farm.monitoring_officer = officer
        farm.save(update_fields=['monitoring_officer'])
        return Response({
            'detail': 'Officer assigned successfully.',
            'farm_id': str(farm.id),
            'officer_id': str(officer.id),
            'officer_name': officer.get_full_name(),
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin], url_path='request_report')
    def request_report(self, request, pk=None):
        """Send a notification to the assigned monitoring officer requesting an audit report."""
        farm = self.get_object()
        if not farm.monitoring_officer:
            return Response({'detail': 'No officer is assigned to this farm.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from notifications.utils import create_notification
            create_notification(
                user=farm.monitoring_officer,
                title='Audit Report Requested',
                message=f'Admin has requested an audit report for {farm.name}. Please submit your field report at your earliest convenience.',
                notification_type='action_required',
            )
        except Exception:
            pass  # Notification failure should not block the response
        return Response({
            'detail': f'Report request sent to {farm.monitoring_officer.get_full_name()}.',
            'farm_id': str(farm.id),
        }, status=status.HTTP_200_OK)


class FarmActivityLogViewSet(viewsets.ModelViewSet):
    serializer_class = FarmActivityLogSerializer
    filter_backends  = [DjangoFilterBackend]
    filterset_fields = ['farm', 'date']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'farmer':
            return FarmActivityLog.objects.filter(farm__owner=user)
        if user.role in ('admin', 'monitoring_officer'):
            return FarmActivityLog.objects.all()
        return FarmActivityLog.objects.none()

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update'):
            return [IsFarmer()]
        return [IsFarmerOrAdmin()]

    def perform_create(self, serializer):
        from django.utils import timezone
        media_file = self.request.FILES.get('media_file')
        captured_at = None
        if media_file:
            # Use provided timestamp or default to now
            raw_ts = self.request.data.get('media_captured_at')
            if raw_ts:
                try:
                    from django.utils.dateparse import parse_datetime
                    captured_at = parse_datetime(raw_ts)
                except Exception:
                    pass
            if not captured_at:
                captured_at = timezone.now()
        serializer.save(logged_by=self.request.user, media_captured_at=captured_at)


class FarmAuditReportViewSet(viewsets.ModelViewSet):
    serializer_class = FarmAuditReportSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == 'farmer':
            return FarmAuditReport.objects.filter(farm__owner=user)
        if user.role == 'monitoring_officer':
            # Officers see all reports but can only edit their own
            return FarmAuditReport.objects.select_related('farm', 'auditor').all()
        if user.role in ('admin', 'investor'):
            return FarmAuditReport.objects.select_related('farm', 'auditor').all()
        return FarmAuditReport.objects.none()

    def get_permissions(self):
        if self.action == 'create':
            # Both monitoring officers and admins can submit audit reports
            return [IsMonitoringOfficerOrAdmin()]
        if self.action in ('update', 'partial_update'):
            # Officers can only update; admins can do anything
            return [IsMonitoringOfficerOrAdmin()]
        if self.action == 'destroy':
            return [IsAdmin()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(auditor=self.request.user)

    def perform_update(self, serializer):
        user = self.request.user
        # Monitoring officers can only edit reports they themselves submitted
        if user.role == 'monitoring_officer':
            instance = self.get_object()
            if instance.auditor != user:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied('You can only edit audit reports you submitted.')
        serializer.save()
