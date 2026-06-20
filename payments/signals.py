from farmasyst_north.sms_service import (
    notify_consumer_order_placed,
    notify_farmer_new_order,
    notify_payment_success,
    notify_payment_failed,
    notify_repayment_success,
    notify_repayment_failed,
)


def send_order_sms(order):
    buyer_phone = order.buyer.phone
    if buyer_phone:
        notify_consumer_order_placed(
            buyer_phone,
            order.reference,
            float(order.total_amount),
        )
    sellers_notified = set()
    for item in order.items.select_related('produce__seller').all():
        seller = item.produce.seller
        if seller.id not in sellers_notified and seller.phone:
            notify_farmer_new_order(
                seller.phone,
                order.reference,
                item.produce.name,
                float(item.quantity),
            )
            sellers_notified.add(seller.id)


def send_payment_sms(order, success: bool, method: str = None):
    phone = order.buyer.phone
    if not phone:
        return
    if success:
        notify_payment_success(
            phone,
            order.reference,
            float(order.total_amount),
            method or order.payment_method,
        )
    else:
        notify_payment_failed(phone, order.reference)


def send_repayment_sms(payment, success: bool, method: str = None):
    """SMS for credit repayment confirmations (InitiateRepaymentView,
    PayFullBalanceView, PaystackWebhookView, MoMoWebhookView._handle_payment).

    Uses the Payment model's fields (payer, amount, reference) — distinct
    from send_payment_sms above, which is for marketplace Order objects.
    """
    phone = getattr(payment.payer, 'phone', None)
    if not phone:
        return
    if success:
        notify_repayment_success(
            phone,
            payment.reference,
            float(payment.amount),
            method or payment.method,
        )
    else:
        notify_repayment_failed(phone, payment.reference)
