# payments/signals.py
from farmasyst_north.sms_service import (
    notify_consumer_order_placed,
    notify_farmer_new_order,
    notify_payment_success,
    notify_payment_failed,
)


def send_order_sms(order):
    """Call this after an Order is created in marketplace/views.py."""
    buyer_phone = order.buyer.phone
    if buyer_phone:
        notify_consumer_order_placed(
            buyer_phone,
            order.reference,
            float(order.total_amount),
        )

    # Notify each seller via their item's produce.seller
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
    """Call this after payment callback in payments/views.py."""
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
