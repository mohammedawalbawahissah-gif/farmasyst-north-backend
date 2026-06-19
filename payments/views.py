from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Disbursement, RepaymentSchedule, Payment, DisbursementRequest
from .serializers import (
    DisbursementSerializer, RepaymentScheduleSerializer,
    PaymentSerializer, InitiateRepaymentSerializer,
    PayFullBalanceSerializer,
    DisbursementRequestSerializer, ApproveDisbursementSerializer,
    RejectDisbursementSerializer,
)
from .services import momo_service, paystack_service, build_momo_callback_url
from accounts.permissions import IsAdmin, IsFarmer, IsInvestor, IsInvestorOrAdmin
from notifications.utils import send_notification


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _generate_repayment_schedule(agreement, disbursement):
    """Create monthly repayment installments for an agreement after disbursement."""
    # Delete any stale schedule rows first (e.g. if re-disbursing)
    RepaymentSchedule.objects.filter(agreement=agreement).delete()

    months    = agreement.repayment_period_months
    principal = Decimal(str(agreement.amount))
    rate      = Decimal(str(agreement.interest_rate)) / Decimal('100')
    total     = principal * (1 + rate)
    installment = (total / months).quantize(Decimal('0.01'))

    start = disbursement.processed_at or timezone.now()
    schedules = []
    for i in range(1, months + 1):
        due = (start + timedelta(days=30 * i)).date()
        schedules.append(RepaymentSchedule(
            agreement=agreement,
            installment_number=i,
            due_date=due,
            amount_due=installment,
        ))
    RepaymentSchedule.objects.bulk_create(schedules)


# ─────────────────────────────────────────────────────────────────────────────
# Repayment Schedule
# ─────────────────────────────────────────────────────────────────────────────

class RepaymentScheduleViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RepaymentScheduleSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == 'farmer':
            return RepaymentSchedule.objects.filter(agreement__farmer=user)
        if user.role == 'investor':
            return RepaymentSchedule.objects.filter(agreement__investor=user)
        if user.role == 'admin':
            return RepaymentSchedule.objects.all()
        return RepaymentSchedule.objects.none()


# ─────────────────────────────────────────────────────────────────────────────
# Repayment Initiation
# ─────────────────────────────────────────────────────────────────────────────

class InitiateRepaymentView(generics.GenericAPIView):
    serializer_class = InitiateRepaymentSerializer
    permission_classes = [IsFarmer]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        schedule = RepaymentSchedule.objects.get(
            id=data['schedule_id'],
            agreement__farmer=request.user
        )

        # Allow payment for any unpaid status
        PAYABLE_STATUSES = {'upcoming', 'due', 'pending', 'overdue'}
        if schedule.status not in PAYABLE_STATUSES:
            return Response(
                {'detail': f'Schedule is already {schedule.status} and cannot be paid.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment = Payment.objects.create(
            payer=request.user,
            payment_type='repayment',
            amount=schedule.amount_due,
            method=data['method'],
            schedule=schedule,
            phone_number=data.get('phone_number', ''),
        )

        if data['method'] == 'momo':
            result = momo_service.request_to_pay(
                amount=str(schedule.amount_due),
                phone=data.get('phone_number', ''),
                reference=payment.reference,
                narration=f'FarmAsyst North repayment — {schedule.agreement.reference}',
                callback_url=build_momo_callback_url(),
            )
            payment.gateway_ref = result.get('reference_id', '')
            payment.gateway_response = result
            payment.status = 'pending' if result.get('success') else 'failed'
            payment.save()
            if result.get('success'):
                send_notification(request.user, 'repayment_due',
                                  'Repayment Initiated',
                                  f'GHS {schedule.amount_due} repayment initiated via MoMo.')

        elif data['method'] == 'paystack':
            result = paystack_service.initialize_transaction(
                email=request.user.email,
                amount_ghs=float(schedule.amount_due),
                reference=payment.reference,
            )
            payment.gateway_response = result
            payment.save()
            if result.get('success'):
                return Response({
                    'payment': PaymentSerializer(payment).data,
                    'authorization_url': result['data'].get('authorization_url'),
                })

        return Response(PaymentSerializer(payment).data)


# ─────────────────────────────────────────────────────────────────────────────
# Full Balance Payment
# ─────────────────────────────────────────────────────────────────────────────

class PayFullBalanceView(generics.GenericAPIView):
    """
    Settle all remaining (upcoming / due / overdue / pending) instalments
    for a credit agreement in a single payment.

    Conditions enforced:
    - The agreement must belong to the requesting farmer.
    - At least one unpaid instalment must exist.
    - This action is irreversible once initiated.
    """
    serializer_class = PayFullBalanceSerializer
    permission_classes = [IsFarmer]

    PAYABLE_STATUSES = {'upcoming', 'due', 'pending', 'overdue'}

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Fetch unpaid schedules for this farmer's agreement
        unpaid = RepaymentSchedule.objects.filter(
            agreement__id=data['agreement_id'],
            agreement__farmer=request.user,
            status__in=self.PAYABLE_STATUSES,
        ).select_related('agreement')

        if not unpaid.exists():
            return Response(
                {'detail': 'No unpaid instalments found for this agreement.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        total = sum(s.amount_due for s in unpaid)
        agreement = unpaid.first().agreement

        # Create a single Payment record representing the full settlement
        payment = Payment.objects.create(
            payer=request.user,
            payment_type='repayment',
            amount=total,
            method=data['method'],
            phone_number=data.get('phone_number', ''),
        )

        if data['method'] == 'momo':
            result = momo_service.request_to_pay(
                amount=str(total),
                phone=data.get('phone_number', ''),
                reference=payment.reference,
                narration=f'FarmAsyst North full settlement — {agreement.reference}',
                callback_url=build_momo_callback_url(),
            )
            payment.gateway_ref = result.get('reference_id', '')
            payment.gateway_response = result
            payment.status = 'pending' if result.get('success') else 'failed'
            payment.save()

            if result.get('success'):
                # Mark all unpaid schedules as paid immediately (optimistic for MoMo)
                now = timezone.now()
                for sched in unpaid:
                    sched.amount_paid = sched.amount_due
                    sched.status = RepaymentSchedule.ScheduleStatus.PAID
                    sched.paid_at = now
                    sched.save()
                send_notification(
                    request.user, 'repayment_due',
                    'Full Balance Payment Initiated',
                    f'GHS {total} full settlement initiated via MoMo for agreement {agreement.reference}.',
                )

        elif data['method'] == 'paystack':
            result = paystack_service.initialize_transaction(
                email=request.user.email,
                amount_ghs=float(total),
                reference=payment.reference,
            )
            payment.gateway_response = result
            payment.save()
            if result.get('success'):
                return Response({
                    'payment': PaymentSerializer(payment).data,
                    'authorization_url': result['data'].get('authorization_url'),
                    'total_amount': str(total),
                    'instalments_count': unpaid.count(),
                })

        return Response({
            'payment': PaymentSerializer(payment).data,
            'total_amount': str(total),
            'instalments_count': unpaid.count(),
        })


# ─────────────────────────────────────────────────────────────────────────────
# Paystack Webhook
# ─────────────────────────────────────────────────────────────────────────────

class PaystackWebhookView(generics.GenericAPIView):
    permission_classes = []

    def post(self, request):
        event = request.data.get('event')
        data  = request.data.get('data', {})
        if event == 'charge.success':
            ref = data.get('reference', '')
            try:
                payment = Payment.objects.get(reference=ref)
                payment.status = 'success'
                payment.save()
                if payment.schedule:
                    payment.schedule.amount_paid = payment.amount
                    payment.schedule.status = 'paid'
                    payment.schedule.paid_at = timezone.now()
                    payment.schedule.save()
                send_notification(payment.payer, 'repayment_received',
                                  'Repayment Confirmed ✅',
                                  f'GHS {payment.amount} payment received.')
            except Payment.DoesNotExist:
                pass
        return Response({'status': 'ok'})


# ─────────────────────────────────────────────────────────────────────────────
# MTN MoMo Webhook
# ─────────────────────────────────────────────────────────────────────────────

class MoMoWebhookView(generics.GenericAPIView):
    """
    Receives the final SUCCESSFUL/FAILED status MTN posts to X-Callback-Url
    once a buyer/farmer approves or declines the USSD prompt on their phone.

    Until now, MoMo orders/repayments stayed stuck on "pending" forever
    because nothing was listening for this callback — request_to_pay only
    confirms the *prompt* was sent, not whether it was accepted.

    Expected MTN payload (sandbox & production use the same shape):
        {
          "financialTransactionId": "...",
          "externalId": "<our Payment.reference or Order.reference>",
          "amount": "...",
          "currency": "GHS",
          "payer": {"partyIdType": "MSISDN", "partyId": "233..."},
          "status": "SUCCESSFUL" | "FAILED",
          "reason": {...}            # present only when status == FAILED
        }

    `externalId` is what we set as `reference` in request_to_pay(), so it's
    either a repayment Payment.reference (PAY-xxxxxx) or a marketplace
    Order.reference (ORD-xxxxx) — we check both.

    If MOMO_WEBHOOK_SECRET is set, the callback URL carries ?key=<secret>
    (see build_momo_callback_url) and requests without a matching key are
    rejected.
    """
    permission_classes = []

    def post(self, request):
        secret = getattr(settings, 'MOMO_WEBHOOK_SECRET', '')
        if secret and request.query_params.get('key') != secret:
            return Response({'detail': 'Invalid or missing key.'}, status=status.HTTP_403_FORBIDDEN)

        data        = request.data
        external_id = (data.get('externalId') or '').strip()
        momo_status = (data.get('status') or '').upper()

        if not external_id or momo_status not in ('SUCCESSFUL', 'FAILED'):
            # Not a status we act on yet (e.g. PENDING) — ack so MTN doesn't retry.
            return Response({'status': 'ignored'})

        payment = Payment.objects.filter(reference=external_id).first()
        if payment:
            self._handle_payment(payment, momo_status, data)
            return Response({'status': 'ok'})

        # Imported here to avoid a module-level payments <-> marketplace cycle.
        from marketplace.models import Order
        order = Order.objects.filter(reference=external_id).first()
        if order:
            self._handle_order(order, momo_status, data)
            return Response({'status': 'ok'})

        return Response({'status': 'ignored', 'detail': 'No matching payment or order.'})

    def _handle_payment(self, payment, momo_status, data):
        if payment.status in ('success', 'failed'):
            return  # already processed — webhook can be retried/duplicated by MTN
        payment.gateway_response = {**payment.gateway_response, 'webhook': dict(data)}

        if momo_status == 'SUCCESSFUL':
            payment.status = 'success'
            payment.save()
            if payment.schedule:
                payment.schedule.amount_paid = payment.amount
                payment.schedule.status = 'paid'
                payment.schedule.paid_at = timezone.now()
                payment.schedule.save()
            send_notification(payment.payer, 'repayment_received',
                              'Repayment Confirmed ✅',
                              f'GHS {payment.amount} MoMo payment received.')
        else:
            payment.status = 'failed'
            payment.save()
            send_notification(payment.payer, 'repayment_due',
                              'MoMo Payment Failed',
                              f'Your GHS {payment.amount} MoMo payment did not go through. Please try again.')

    def _handle_order(self, order, momo_status, data):
        if order.status in ('confirmed', 'cancelled'):
            return  # already processed
        order.payment_reference = data.get('financialTransactionId', order.payment_reference)

        if momo_status == 'SUCCESSFUL':
            order.status = 'confirmed'
            order.save(update_fields=['status', 'payment_reference'])

            send_notification(order.buyer, 'payment',
                              'Payment confirmed ✅',
                              f'Your GHS {float(order.total_amount):,.2f} MoMo payment for order {order.reference} was confirmed.')
            for item in order.items.select_related('produce__seller'):
                send_notification(item.produce.seller, 'payment',
                                  f'Payment received — {order.reference}',
                                  f'MoMo payment of GHS {float(order.total_amount):,.2f} confirmed for order {order.reference}. Please prepare the order.')
        else:
            order.status = 'cancelled'
            order.save(update_fields=['status', 'payment_reference'])

            # Stock was decremented optimistically when the order was placed —
            # since payment failed, give it back to the listing.
            for item in order.items.select_related('produce'):
                produce = item.produce
                produce.quantity_available = produce.quantity_available + item.quantity
                if produce.status == 'sold_out':
                    produce.status = 'active'
                produce.save(update_fields=['quantity_available', 'status'])

            send_notification(order.buyer, 'payment',
                              'Payment failed',
                              f'Your MoMo payment for order {order.reference} was not approved. The order has been cancelled and the item put back in stock.')


# ─────────────────────────────────────────────────────────────────────────────
# Legacy Disbursement (admin direct)
# ─────────────────────────────────────────────────────────────────────────────

class DisbursementViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only view of disbursements. Creation happens via DisbursementRequestViewSet."""
    serializer_class = DisbursementSerializer
    permission_classes = [IsInvestorOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return Disbursement.objects.all()
        if user.role == 'investor':
            return Disbursement.objects.filter(agreement__investor=user)
        return Disbursement.objects.none()


# ─────────────────────────────────────────────────────────────────────────────
# Disbursement Request Workflow
# ─────────────────────────────────────────────────────────────────────────────

class DisbursementRequestViewSet(viewsets.ModelViewSet):
    serializer_class = DisbursementRequestSerializer

    def get_permissions(self):
        if self.action in ['approve', 'reject', 'list', 'retrieve']:
            if self.request.user.is_authenticated and self.request.user.role == 'admin':
                return [IsAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return DisbursementRequest.objects.select_related(
                'agreement', 'agreement__farmer', 'agreement__investor',
                'requested_by', 'reviewed_by', 'disbursement'
            ).all()
        if user.role == 'investor':
            return DisbursementRequest.objects.filter(requested_by=user).select_related(
                'agreement', 'agreement__farmer', 'disbursement'
            )
        if user.role == 'farmer':
            return DisbursementRequest.objects.filter(
                agreement__farmer=user
            ).select_related('agreement', 'disbursement')
        return DisbursementRequest.objects.none()

    def perform_create(self, serializer):
        agreement = serializer.validated_data['agreement']

        # Guard: agreement must be active
        if agreement.status != 'active':
            from rest_framework.exceptions import ValidationError
            raise ValidationError('Disbursement can only be requested for an active agreement.')

        # Guard: no duplicate pending or approved request
        if DisbursementRequest.objects.filter(agreement=agreement, status__in=['pending', 'approved']).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError('An active disbursement request already exists for this agreement.')

        req = serializer.save(
            requested_by=self.request.user,
            amount=agreement.amount,
        )

        # Notify admin
        from accounts.models import User
        for admin in User.objects.filter(role='admin'):
            send_notification(
                admin, 'disbursement_requested',
                'Disbursement Request',
                f'Investor {req.requested_by.get_full_name()} requested disbursement '
                f'of GHS {req.amount} for agreement {agreement.reference}.'
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def approve(self, request, pk=None):
        dr = self.get_object()
        if dr.status != 'pending':
            return Response({'detail': 'Only pending requests can be approved.'},
                            status=status.HTTP_400_BAD_REQUEST)

        ser = ApproveDisbursementSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        method = ser.validated_data['method']
        notes  = ser.validated_data.get('notes', '')

        agreement = dr.agreement
        farmer    = agreement.farmer
        investor  = agreement.investor

        # Create the Disbursement record
        disbursement = Disbursement.objects.create(
            agreement=agreement,
            amount=dr.amount,
            method=method,
            disbursed_by=request.user,
            notes=notes,
            status='processing',
        )

        # Attempt gateway payout (MoMo only for now)
        if method == 'momo':
            result = momo_service.transfer(
                amount=str(dr.amount),
                phone=farmer.phone if hasattr(farmer, 'phone') else '',
                reference=disbursement.reference,
                narration=f'FarmAsyst North disbursement — {agreement.reference}',
            )
            disbursement.gateway_ref = result.get('reference_id', '')
            disbursement.gateway_response = result
            disbursement.status = 'processing' if result.get('success') else 'failed'
        else:
            disbursement.status = 'processing'

        disbursement.processed_at = timezone.now()
        disbursement.save()

        # Update disbursement request
        dr.status      = 'approved'
        dr.reviewed_by = request.user
        dr.reviewed_at = timezone.now()
        dr.disbursement = disbursement
        dr.save()

        # Mark agreement as disbursed
        agreement.disbursed_at = timezone.now()
        agreement.save()

        # Generate repayment schedule
        _generate_repayment_schedule(agreement, disbursement)

        # Notify both parties
        send_notification(
            farmer, 'disbursement',
            'Funds Disbursed 🎉',
            f'GHS {dr.amount} has been disbursed under agreement {agreement.reference}. '
            f'Your repayment schedule is now available.'
        )
        send_notification(
            investor, 'disbursement_approved',
            'Disbursement Approved ✅',
            f'Your disbursement request for {agreement.reference} has been approved. '
            f'GHS {dr.amount} is being processed to the farmer.'
        )

        return Response(DisbursementRequestSerializer(dr).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def reject(self, request, pk=None):
        dr = self.get_object()
        if dr.status != 'pending':
            return Response({'detail': 'Only pending requests can be rejected.'},
                            status=status.HTTP_400_BAD_REQUEST)

        ser = RejectDisbursementSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        dr.status           = 'rejected'
        dr.reviewed_by      = request.user
        dr.reviewed_at      = timezone.now()
        dr.rejection_reason = ser.validated_data['reason']
        dr.save()

        send_notification(
            dr.requested_by, 'disbursement_rejected',
            'Disbursement Request Rejected',
            f'Your disbursement request for agreement {dr.agreement.reference} was rejected. '
            f'Reason: {dr.rejection_reason}'
        )

        return Response(DisbursementRequestSerializer(dr).data)
