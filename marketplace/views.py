from decimal import Decimal
import logging
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.conf import settings
from .models import Produce, Order, OrderItem, ProduceReview
from .serializers import ProduceSerializer, OrderSerializer, ProduceReviewSerializer
from accounts.permissions import IsFarmer, IsAdmin
from notifications.models import Notification
from payments.services import momo_service, hubtel_payment_service, build_momo_callback_url, build_hubtel_callback_url
from payments.signals import send_order_sms

logger = logging.getLogger(__name__)


def _notify(recipient, notif_type, title, body, data=None):
    try:
        Notification.objects.create(
            recipient=recipient, notif_type=notif_type,
            title=title, body=body, data=data or {},
        )
    except Exception:
        pass


class ProduceViewSet(viewsets.ModelViewSet):
    serializer_class = ProduceSerializer
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['produce_type', 'status', 'is_organic']
    search_fields    = ['name', 'farm__name', 'farm__region', 'farm__district']
    ordering_fields  = ['price', 'avg_rating', 'created_at']

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Produce.objects.filter(status='active')
        if user.role == 'farmer':
            return Produce.objects.filter(seller=user)
        return Produce.objects.filter(status='active')

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsFarmer()]
        return [AllowAny()]

    def perform_create(self, serializer):
        serializer.save(
            seller=self.request.user,
            farm_id=self.request.data.get('farm'),
        )


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class   = OrderSerializer
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ['status']
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'consumer':
            return Order.objects.prefetch_related('items__produce').filter(buyer=user)
        if user.role == 'farmer':
            return Order.objects.prefetch_related('items__produce').filter(
                items__produce__seller=user
            ).distinct()
        if user.role == 'admin':
            return Order.objects.prefetch_related('items__produce').all()
        return Order.objects.none()

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        data           = request.data
        produce_id     = data.get('produce_id')
        delivery_type  = data.get('delivery_type', 'pickup')
        delivery_addr  = data.get('delivery_address', '') or ''
        delivery_date  = data.get('delivery_date') or None
        notes          = data.get('notes', '') or ''
        raw_pm = data.get('payment_method', 'momo')
        pm_map = {
            'instant': 'momo', 'momo': 'momo',
            'hubtel_momo': 'hubtel_momo',
            'card': 'card', 'paystack': 'card', 'hubtel': 'card',
            'bank_transfer': 'bank_transfer',
            'cod': 'cash_on_delivery', 'cash_on_delivery': 'cash_on_delivery',
        }
        payment_method = pm_map.get(raw_pm, 'cash_on_delivery')

        try:
            quantity = Decimal(str(data.get('quantity', 1)))
        except Exception:
            quantity = Decimal('1')

        if not produce_id:
            return Response({'detail': 'produce_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            produce = Produce.objects.select_related('seller', 'farm').get(
                id=produce_id, status='active'
            )
        except Produce.DoesNotExist:
            return Response(
                {'detail': 'Produce not found or no longer available.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if delivery_type == 'delivery' and not delivery_addr.strip():
            return Response(
                {'detail': 'Delivery address is required for home delivery.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subtotal = produce.price * quantity

        order = Order.objects.create(
            buyer            = request.user,
            delivery_type    = delivery_type,
            delivery_address = delivery_addr,
            delivery_date    = delivery_date,
            notes            = notes,
            total_amount     = subtotal,
            status           = Order.OrderStatus.PENDING,
            payment_method   = payment_method,
        )

        OrderItem.objects.create(
            order      = order,
            produce    = produce,
            quantity   = quantity,
            unit_price = produce.price,
            subtotal   = subtotal,
        )

        produce.quantity_available = max(Decimal('0'), produce.quantity_available - quantity)
        produce.total_orders       = produce.total_orders + 1
        if produce.quantity_available == 0:
            produce.status = 'sold_out'
        produce.save()

        buyer_name     = request.user.get_full_name() or request.user.email
        farm_name      = produce.farm.name if produce.farm else 'your farm'
        delivery_label = 'Farm Pickup' if delivery_type == 'pickup' else 'Home Delivery'

        _notify(
            recipient  = produce.seller,
            notif_type = 'order_update',
            title      = f'New order — {produce.name}',
            body       = (
                f'{buyer_name} ordered {quantity} {produce.unit} of {produce.name} '
                f'(GHS {float(subtotal):,.2f}). Fulfilment: {delivery_label}. '
                f'Payment: {payment_method}. Ref: {order.reference}.'
            ),
            data={'order_id': str(order.id), 'order_reference': order.reference},
        )
        _notify(
            recipient  = request.user,
            notif_type = 'order_update',
            title      = f'Order placed — {order.reference}',
            body       = (
                f'Your order for {quantity} {produce.unit} of {produce.name} '
                f'from {farm_name} was placed successfully.'
            ),
            data={'order_id': str(order.id), 'order_reference': order.reference},
        )

        send_order_sms(order)

        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='initiate_payment')
    def initiate_payment(self, request, pk=None):
        """
        Initiate real payment for an existing order.

        For MoMo: sends a mobile money prompt to the buyer's phone (MTN direct).
        For hubtel_momo: redirects to Hubtel Checkout for Telecel/AirtelTigo/MTN
                   mobile money — checkout_url to redirect the buyer to.
        For card:  initializes a Hubtel Checkout transaction and returns the
                   checkout_url to redirect the buyer to.
        For bank_transfer: returns bank account details.
        For cash_on_delivery: no-op (confirm immediately).

        Request body:
          - phone_number  (str, required for momo and hubtel_momo)
        """
        order = self.get_object()

        # Only the buyer can initiate payment
        if order.buyer != request.user:
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        if order.status not in ('pending',):
            return Response(
                {'detail': f'Cannot initiate payment for an order with status "{order.status}".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment_method = order.payment_method
        total = float(order.total_amount)

        # ── Cash on delivery ────────────────────────────────────────────────
        if payment_method == 'cash_on_delivery':
            return Response({
                'payment_method': 'cash_on_delivery',
                'message': 'No online payment needed. Pay on delivery.',
                'order': OrderSerializer(order).data,
            })

        # ── Bank Transfer ────────────────────────────────────────────────────
        if payment_method == 'bank_transfer':
            return Response({
                'payment_method': 'bank_transfer',
                'bank_name':      'Stanbic Bank Ghana',
                'account_name':   'FarmAsyst North Ltd',
                'account_number': '9040008877142',
                'amount':         total,
                'reference':      order.reference,
                'message':        f'Transfer GHS {total:,.2f} and use {order.reference} as your payment reference.',
                'order': OrderSerializer(order).data,
            })

        # ── MoMo ─────────────────────────────────────────────────────────────
        if payment_method == 'momo':
            phone = request.data.get('phone_number', '').strip()
            if not phone or len(phone) < 10:
                return Response(
                    {'detail': 'A valid MoMo phone number is required.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Normalize phone: strip leading 0, add 233 country code
            if phone.startswith('0'):
                phone = '233' + phone[1:]
            elif not phone.startswith('233'):
                phone = '233' + phone

            result = momo_service.request_to_pay(
                amount    = f'{total:.2f}',  # MoMo uses GHS (not pesewas)
                phone     = phone,
                reference = order.reference,
                narration = f'Payment for FarmAsyst order {order.reference}',
                callback_url = build_momo_callback_url(),
            )

            if result.get('success'):
                # Store the MoMo reference for webhook reconciliation
                order.payment_reference = result.get('reference_id', '')
                order.save(update_fields=['payment_reference'])

                _notify(
                    recipient  = order.buyer,
                    notif_type = 'payment',
                    title      = 'MoMo prompt sent',
                    body       = f'A payment prompt of GHS {total:,.2f} has been sent to {request.data.get("phone_number")}. Approve it on your phone to complete your order.',
                    data       = {'order_id': str(order.id)},
                )
                return Response({
                    'payment_method': 'momo',
                    'message':        f'A MoMo prompt of GHS {total:,.2f} has been sent to {request.data.get("phone_number")}. Approve it on your phone.',
                    'reference_id':   result.get('reference_id'),
                    'order':          OrderSerializer(order).data,
                })
            else:
                logger.error('MoMo initiate_payment failed for order=%s: %s', order.reference, result)
                return Response(
                    {'detail': result.get('detail', 'Could not send MoMo prompt. Please check the number and try again.'),
                     'error':  result.get('error', '')},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        # ── Card or Mobile Money (Other Networks) via Hubtel Checkout ────────
        if payment_method in ('card', 'hubtel_momo'):
            payee_mobile = ''
            if payment_method == 'hubtel_momo':
                payee_mobile = request.data.get('phone_number', '').strip()
                if not payee_mobile or len(payee_mobile) < 10:
                    return Response(
                        {'detail': 'A valid Mobile Money number is required.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            frontend_base = getattr(settings, 'FRONTEND_URL', 'https://farmasyst-north-frontend.onrender.com')
            return_url       = f'{frontend_base}/consumer/orders?ref={order.reference}'
            cancellation_url = f'{frontend_base}/consumer/marketplace'
            description = (
                f'FarmAsyst order {order.reference}' if payment_method == 'card'
                else f'FarmAsyst order {order.reference} (Mobile Money)'
            )

            result = hubtel_payment_service.initiate_checkout(
                amount_ghs        = total,
                description       = description,
                client_reference  = order.reference,
                callback_url      = build_hubtel_callback_url(),
                return_url        = return_url,
                cancellation_url  = cancellation_url,
                payee_name        = request.user.get_full_name() or '',
                payee_mobile      = payee_mobile,
                payee_email       = request.user.email or '',
            )

            if result.get('success'):
                checkout_url = result.get('checkout_url', '')
                title = 'Complete your card payment' if payment_method == 'card' else 'Complete your Mobile Money payment'
                _notify(
                    recipient  = order.buyer,
                    notif_type = 'payment',
                    title      = title,
                    body       = f'Click the link to complete payment of GHS {total:,.2f} for order {order.reference}.',
                    data       = {'order_id': str(order.id), 'checkout_url': checkout_url},
                )
                return Response({
                    'payment_method': payment_method,
                    'checkout_url':   checkout_url,
                    'checkout_id':    result.get('checkout_id', ''),
                    'reference':      order.reference,
                    'message':        'Redirect the user to checkout_url to complete payment via Hubtel.',
                    'order':          OrderSerializer(order).data,
                })
            else:
                return Response(
                    {'detail': 'Could not initialize payment. Please try again.',
                     'error':  result.get('detail') or result.get('error', '')},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        return Response({'detail': f'Unsupported payment method: {payment_method}.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='verify_payment')
    def verify_payment(self, request, pk=None):
        """
        Check the current status of a card order after the buyer returns
        from the Hubtel checkout page (via returnUrl).

        Real confirmation happens asynchronously via HubtelWebhookView,
        same as the MoMo flow — this endpoint just reports whatever the
        order's status is by the time the buyer lands back on the site.
        If the webhook hasn't arrived yet (rare — Hubtel's docs say allow
        up to 5 minutes), this will report 'pending' and the frontend
        should poll or prompt the user to wait briefly.

        Request body:
          - reference  (str, optional) — included for compatibility, not
                       currently used since lookup is by order id.
        """
        order = self.get_object()

        if order.status == 'confirmed':
            return Response({
                'status':  'confirmed',
                'message': 'Payment verified and order confirmed.',
                'order':   OrderSerializer(order).data,
            })
        elif order.status == 'cancelled':
            return Response(
                {'detail': 'Payment was not approved. The order has been cancelled.',
                 'status': 'cancelled'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        else:
            return Response(
                {'detail': 'Payment not yet confirmed. If you just paid, please wait a few moments and check again.',
                 'status': 'pending'},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        order = self.get_object()
        if order.status != 'pending':
            return Response({'detail': 'Only pending orders can be confirmed.'}, status=400)
        order.status = 'confirmed'
        order.save()
        _notify(
            recipient  = order.buyer,
            notif_type = 'order_update',
            title      = f'Order confirmed — {order.reference}',
            body       = f'The farmer confirmed your order {order.reference}. Preparing for {order.get_delivery_type_display().lower()}.',
            data={'order_id': str(order.id)},
        )
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        order = self.get_object()
        if order.status not in ('pending', 'confirmed'):
            return Response({'detail': 'Cannot cancel at this stage.'}, status=400)
        order.status = 'cancelled'
        order.save()

        # Give back stock that was optimistically deducted at order creation.
        for item in order.items.select_related('produce'):
            produce = item.produce
            produce.quantity_available = produce.quantity_available + item.quantity
            if produce.status == 'sold_out':
                produce.status = 'active'
            produce.save(update_fields=['quantity_available', 'status'])

        if request.user.role == 'farmer':
            _notify(
                recipient  = order.buyer,
                notif_type = 'order_update',
                title      = f'Order cancelled — {order.reference}',
                body       = f'Your order {order.reference} was cancelled by the seller.',
                data={'order_id': str(order.id)},
            )
        return Response(OrderSerializer(order).data)


class ProduceReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ProduceReviewSerializer

    def get_queryset(self):
        return ProduceReview.objects.filter(produce_id=self.kwargs['produce_pk'])

    def perform_create(self, serializer):
        serializer.save(
            reviewer=self.request.user,
            produce_id=self.kwargs['produce_pk'],
        )
