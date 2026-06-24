from django.utils import timezone
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import CreditApplication, ApplicationDocument, CreditAgreement
from .serializers import (CreditApplicationSerializer, CreditApplicationAdminSerializer,
                          ApplicationDocumentSerializer, CreditAgreementSerializer)
from accounts.permissions import IsFarmer, IsAdmin, IsInvestorOrAdmin, IsFarmerOrAdmin
from notifications.utils import send_notification
from credit.signals import send_credit_status_sms


class CreditApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = CreditApplicationSerializer
    filter_backends  = [DjangoFilterBackend]
    filterset_fields = ['status', 'credit_type']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'farmer':
            return CreditApplication.objects.filter(farmer=user)
        if user.role == 'admin':
            return CreditApplication.objects.all()
        if user.role == 'investor':
            return CreditApplication.objects.filter(matched_investor=user)
        return CreditApplication.objects.none()

    def get_serializer_class(self):
        if self.request.user.role == 'admin':
            return CreditApplicationAdminSerializer
        return CreditApplicationSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update'):
            return [IsFarmer()]
        if self.action in ('list', 'retrieve', 'accept', 'decline_match'):
            return [IsAuthenticated()]
        return [IsFarmerOrAdmin()]

    def perform_create(self, serializer):
        serializer.save(farmer=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsFarmer])
    def submit(self, request, pk=None):
        app = self.get_object()
        if app.status != 'draft':
            return Response({'detail': 'Only draft applications can be submitted.'}, status=400)
        old_status = app.status
        app.status = 'submitted'
        app.submitted_at = timezone.now()
        app.credit_score_at_submission = request.user.farmer_profile.credit_score if hasattr(request.user, 'farmer_profile') else 0
        app.save()
        send_notification(app.farmer, 'application_status',
                          'Application Submitted',
                          f'Your application {app.reference} has been submitted for review.')
        send_credit_status_sms(app, old_status)
        return Response(CreditApplicationSerializer(app).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def approve(self, request, pk=None):
        app = self.get_object()
        old_status = app.status
        app.status = 'approved'
        app.reviewer = request.user
        app.reviewer_notes = request.data.get('notes', '')
        app.reviewed_at = timezone.now()
        app.approved_at = timezone.now()
        app.save()
        send_notification(app.farmer, 'application_status',
                          'Application Approved 🎉',
                          f'Your application {app.reference} has been approved.')
        send_credit_status_sms(app, old_status)
        return Response(CreditApplicationAdminSerializer(app).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def reject(self, request, pk=None):
        app = self.get_object()
        old_status = app.status
        app.status = 'rejected'
        app.reviewer = request.user
        app.reviewer_notes = request.data.get('notes', '')
        app.rejection_reason = request.data.get('reason', '')
        app.reviewed_at = timezone.now()
        app.save()
        send_notification(app.farmer, 'application_status',
                          'Application Not Approved',
                          f'Your application {app.reference} was not approved. Reason: {app.rejection_reason}')
        send_credit_status_sms(app, old_status)
        return Response(CreditApplicationAdminSerializer(app).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def decline(self, request, pk=None):
        app = self.get_object()
        if app.status not in ('approved', 'matched'):
            return Response({'detail': 'Can only decline approved or matched applications.'}, status=400)
        old_status = app.status
        app.status = 'under_review'
        app.matched_investor = None
        app.reviewer_notes = request.data.get('notes', app.reviewer_notes)
        app.save()
        send_notification(app.farmer, 'application_status',
                          'Application Under Review Again',
                          f'Your application {app.reference} is being re-reviewed.')
        send_credit_status_sms(app, old_status)
        return Response(CreditApplicationAdminSerializer(app).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def match(self, request, pk=None):
        app = self.get_object()
        if app.status not in ('approved', 'scored', 'submitted', 'under_review'):
            return Response({'detail': 'Application cannot be matched at this stage.'}, status=400)
        investor_id = request.data.get('investor')
        if not investor_id:
            return Response({'detail': 'investor is required.'}, status=400)
        from accounts.models import User
        try:
            investor = User.objects.get(id=investor_id, role='investor')
        except User.DoesNotExist:
            return Response({'detail': 'Investor not found.'}, status=404)
        old_status = app.status
        app.matched_investor = investor
        app.status = 'matched'
        app.save()
        send_notification(app.farmer, 'application_status',
                          'Application Matched',
                          f'Your application {app.reference} has been matched to an investor.')
        send_notification(investor, 'new_opportunity',
                          'New Investment Opportunity',
                          f'A new farmer application has been matched to you. Check your Opportunities page.')
        send_credit_status_sms(app, old_status)
        return Response(CreditApplicationAdminSerializer(app).data)

    @action(detail=True, methods=['post'], permission_classes=[IsInvestorOrAdmin])
    def accept(self, request, pk=None):
        app = self.get_object()
        user = request.user
        if app.status != 'matched':
            return Response({'detail': 'Application is not in matched status.'}, status=400)
        if user.role == 'investor' and app.matched_investor != user:
            return Response({'detail': 'This application is not matched to you.'}, status=403)
        agreement = CreditAgreement.objects.create(
            application=app,
            investor=app.matched_investor,
            farmer=app.farmer,
            credit_type=app.credit_type,
            amount=app.amount_requested or 0,
            repayment_period_months=app.repayment_period_months or 12,
        )
        old_status = app.status
        app.status = 'agreement'
        app.save()
        send_notification(app.farmer, 'agreement_created',
                          'Contract Ready for Signature',
                          f'An investment agreement for {app.reference} is ready for your signature.')
        send_credit_status_sms(app, old_status)
        return Response(CreditAgreementSerializer(agreement).data, status=201)

    @action(detail=True, methods=['post'], permission_classes=[IsInvestorOrAdmin])
    def decline_match(self, request, pk=None):
        app = self.get_object()
        user = request.user
        if user.role == 'investor' and app.matched_investor != user:
            return Response({'detail': 'This application is not matched to you.'}, status=403)
        old_status = app.status
        app.status = 'approved'
        app.matched_investor = None
        app.save()
        send_notification(app.farmer, 'application_status',
                          'Re-matching in Progress',
                          f'Your application {app.reference} is being re-matched to another investor.')
        send_credit_status_sms(app, old_status)
        return Response(CreditApplicationAdminSerializer(app).data)


class DocumentUploadView(generics.CreateAPIView):
    serializer_class = ApplicationDocumentSerializer
    permission_classes = [IsFarmer]

    def perform_create(self, serializer):
        app_id = self.kwargs['application_id']
        app = CreditApplication.objects.get(id=app_id, farmer=self.request.user)
        file = self.request.FILES.get('file')
        serializer.save(application=app, original_name=file.name if file else '')


class CreditAgreementViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CreditAgreementSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == 'farmer':
            return CreditAgreement.objects.filter(farmer=user)
        if user.role == 'investor':
            return CreditAgreement.objects.filter(investor=user)
        if user.role == 'admin':
            return CreditAgreement.objects.all()
        return CreditAgreement.objects.none()

    @action(detail=True, methods=['post'])
    def sign(self, request, pk=None):
        agreement = self.get_object()
        user = request.user
        now = timezone.now()
        if user.role == 'farmer' and agreement.farmer == user:
            agreement.farmer_signed_at = now
        elif user.role == 'investor' and agreement.investor == user:
            agreement.investor_signed_at = now
        else:
            return Response({'detail': 'Not authorised to sign this contract.'}, status=403)
        if agreement.farmer_signed_at and agreement.investor_signed_at:
            agreement.status = 'active'
            app = agreement.application
            if app.status != 'disbursed':
                old_status = app.status
                app.status = 'disbursed'
                app.save()
                send_credit_status_sms(app, old_status)
        agreement.save()
        return Response(CreditAgreementSerializer(agreement).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def generate_document(self, request, pk=None):
        agreement = self.get_object()
        user = request.user
        if user not in (agreement.farmer, agreement.investor) and user.role != 'admin':
            return Response({'detail': 'Not authorised to generate this contract.'}, status=403)
        if agreement.contract_document:
            return Response(CreditAgreementSerializer(agreement).data)

        lines = [
            "FARMASYST NORTH — INVESTMENT AGREEMENT",
            "=" * 50,
            f"Reference:          {agreement.reference}",
            f"Credit Type:        {agreement.credit_type}",
            f"Amount:             GHS {agreement.amount}",
            f"Repayment Period:   {agreement.repayment_period_months} months",
            f"Interest Rate:      {agreement.interest_rate}%",
            f"Farmer:             {agreement.farmer.get_full_name()} ({agreement.farmer.email})",
            f"Investor:           {agreement.investor.get_full_name()} ({agreement.investor.email})",
            f"Created:            {agreement.created_at.strftime('%d %B %Y')}",
            "",
            "TERMS AND CONDITIONS",
            "-" * 50,
            "1. The Investor agrees to provide the above amount to the Farmer for the stated purpose.",
            "2. The Farmer agrees to repay the full amount plus interest within the repayment period.",
            "3. FarmAsyst North facilitates this agreement and is not a party to the loan.",
            "4. Disbursement will occur after both parties have signed this agreement.",
            "5. Repayment schedules will be provided separately by FarmAsyst North.",
            "",
            "SIGNATURES",
            "-" * 50,
            f"Farmer signature:   {'[SIGNED]' if agreement.farmer_signed_at else '[PENDING]'}",
            f"Investor signature: {'[SIGNED]' if agreement.investor_signed_at else '[PENDING]'}",
            "",
            "This document is generated electronically by FarmAsyst North.",
        ]
        content = "\n".join(lines)

        from django.core.files.base import ContentFile
        filename = f"contract_{agreement.reference}.txt"
        agreement.contract_document.save(filename, ContentFile(content.encode('utf-8')), save=True)
        send_notification(
            agreement.farmer, 'contract_generated',
            'Contract Document Ready',
            f'The investment agreement {agreement.reference} is ready. Please review and sign.'
        )
        send_notification(
            agreement.investor, 'contract_generated',
            'Contract Document Ready',
            f'The investment agreement {agreement.reference} is ready. Please review and sign.'
        )
        return Response(CreditAgreementSerializer(agreement).data)


# ── Project Applications ──────────────────────────────────────────────────────

from .models import ProjectApplication, ProjectFarmerEntry
from .serializers import (ProjectApplicationSerializer, ProjectApplicationAdminSerializer,
                           ProjectFarmerEntrySerializer)


class ProjectApplicationViewSet(viewsets.ModelViewSet):
    """
    Organisation-based group credit applications (Projects).
    Investors/organisations submit; admins review.
    """
    filter_backends  = [DjangoFilterBackend]
    filterset_fields = ['status', 'credit_type']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return ProjectApplication.objects.prefetch_related('farmer_entries').all()
        if user.role == 'investor':
            return ProjectApplication.objects.prefetch_related('farmer_entries').filter(submitted_by=user)
        return ProjectApplication.objects.none()

    def get_serializer_class(self):
        if self.request.user.role == 'admin':
            return ProjectApplicationAdminSerializer
        return ProjectApplicationSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update'):
            return [IsInvestorOrAdmin()]
        if self.action in ('submit', 'withdraw'):
            return [IsInvestorOrAdmin()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(submitted_by=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsInvestorOrAdmin])
    def submit(self, request, pk=None):
        project = self.get_object()
        if project.status != 'draft':
            return Response({'detail': 'Only draft projects can be submitted.'}, status=400)
        if not project.farmer_entries.exists():
            return Response({'detail': 'Add at least one farmer entry before submitting.'}, status=400)
        project.status = 'submitted'
        project.submitted_at = timezone.now()
        project.save()
        from notifications.utils import notify_admins
        notify_admins(
            'project_submitted', f'Project Application Submitted: {project.project_name}',
            f'{project.organisation} submitted project {project.reference} covering '
            f'{project.farmer_entries.count()} farmer(s).',
            priority='high',
        )
        return Response(ProjectApplicationSerializer(project).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def approve(self, request, pk=None):
        project = self.get_object()
        project.status = 'approved'
        project.reviewer = request.user
        project.reviewer_notes = request.data.get('notes', '')
        project.reviewed_at = timezone.now()
        project.save()
        if project.submitted_by:
            from notifications.utils import send_notification
            send_notification(
                project.submitted_by, 'project_status',
                f'Project Approved: {project.project_name}',
                f'Your project application {project.reference} has been approved.',
            )
        return Response(ProjectApplicationAdminSerializer(project).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def reject(self, request, pk=None):
        project = self.get_object()
        project.status = 'rejected'
        project.reviewer = request.user
        project.rejection_reason = request.data.get('reason', '')
        project.reviewer_notes = request.data.get('notes', '')
        project.reviewed_at = timezone.now()
        project.save()
        if project.submitted_by:
            from notifications.utils import send_notification
            send_notification(
                project.submitted_by, 'project_status',
                f'Project Not Approved: {project.project_name}',
                f'Your project {project.reference} was not approved. Reason: {project.rejection_reason}',
            )
        return Response(ProjectApplicationAdminSerializer(project).data)

    @action(detail=True, methods=['post'], permission_classes=[IsInvestorOrAdmin])
    def withdraw(self, request, pk=None):
        project = self.get_object()
        if project.status in ('approved', 'disbursed'):
            return Response({'detail': 'Cannot withdraw an approved or disbursed project.'}, status=400)
        project.status = 'withdrawn'
        project.save()
        return Response(ProjectApplicationSerializer(project).data)

    @action(detail=True, methods=['post'], permission_classes=[IsInvestorOrAdmin],
            url_path='add_farmer')
    def add_farmer(self, request, pk=None):
        """Add a farmer entry to a draft project."""
        project = self.get_object()
        if project.status != 'draft':
            return Response({'detail': 'Can only add farmers to draft projects.'}, status=400)
        serializer = ProjectFarmerEntrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(project=project)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], permission_classes=[IsInvestorOrAdmin],
            url_path=r'remove_farmer/(?P<entry_id>[^/.]+)')
    def remove_farmer(self, request, pk=None, entry_id=None):
        """Remove a farmer entry from a draft project."""
        project = self.get_object()
        if project.status != 'draft':
            return Response({'detail': 'Can only remove farmers from draft projects.'}, status=400)
        try:
            entry = ProjectFarmerEntry.objects.get(id=entry_id, project=project)
            entry.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProjectFarmerEntry.DoesNotExist:
            return Response({'detail': 'Farmer entry not found.'}, status=404)
