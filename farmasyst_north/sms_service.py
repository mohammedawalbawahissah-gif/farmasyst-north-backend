import logging
import africastalking
from django.conf import settings

logger = logging.getLogger(__name__)

africastalking.initialize(
    username=settings.AFRICASTALKING_USERNAME,
    api_key=settings.AFRICASTALKING_API_KEY,
)
sms = africastalking.SMS


def _normalize_gh_phone(phone: str) -> str:
    """Convert local Ghana format (0XXXXXXXXX) to E.164 (+233XXXXXXXXX).

    Africa's Talking rejects local-format numbers outright, so every
    outbound SMS must be normalized before it reaches the API. This is
    applied once, here, so every caller in this file is covered
    automatically.
    """
    phone = (phone or "").strip().replace(" ", "")
    if phone.startswith("+233"):
        return phone
    if phone.startswith("233"):
        return "+" + phone
    if phone.startswith("0"):
        return "+233" + phone[1:]
    if phone.startswith("+"):
        return phone
    return "+233" + phone


def _send(recipients, message):
    recipients = [_normalize_gh_phone(p) for p in recipients]
    try:
        response = sms.send(message, recipients)
        logger.info("SMS sent: %s", response)
    except Exception as exc:
        logger.error("SMS failed to %s: %s", recipients, exc)


def notify_consumer_order_placed(phone, order_ref, amount):
    _send([phone], f"FarmAsyst: Your order #{order_ref} of GHS {amount:.2f} has been placed. We will notify you when it ships.")

def notify_farmer_new_order(phone, order_ref, product, qty):
    _send([phone], f"FarmAsyst: New order #{order_ref} received for {qty} unit(s) of {product}. Log in to confirm.")

def notify_payment_success(phone, order_ref, amount, method):
    _send([phone], f"FarmAsyst: Payment of GHS {amount:.2f} via {method} confirmed for order #{order_ref}. Thank you!")

def notify_payment_failed(phone, order_ref):
    _send([phone], f"FarmAsyst: Payment for order #{order_ref} was not completed. Please retry or contact support.")

def notify_repayment_success(phone, payment_ref, amount, method):
    _send([phone], f"FarmAsyst: Repayment of GHS {amount:.2f} via {method} confirmed (ref #{payment_ref}). Thank you!")

def notify_repayment_failed(phone, payment_ref):
    _send([phone], f"FarmAsyst: Your repayment (ref #{payment_ref}) did not go through. Please retry or contact support.")

def send_otp(phone, otp):
    _send([phone], f"FarmAsyst verification code: {otp}. Valid for 10 minutes. Do not share this code.")

def notify_credit_submitted(phone, ref):
    _send([phone], f"FarmAsyst: Your credit application #{ref} has been submitted and is under review.")

def notify_credit_under_review(phone, ref):
    _send([phone], f"FarmAsyst: Your credit application #{ref} is now under review. We will update you soon.")

def notify_credit_approved(phone, ref, amount):
    _send([phone], f"FarmAsyst: Congratulations! Your credit application #{ref} for GHS {amount:.2f} has been approved.")

def notify_credit_declined(phone, ref):
    _send([phone], f"FarmAsyst: Your credit application #{ref} was not approved at this time. Contact support for details.")

def notify_credit_agreement(phone, ref):
    _send([phone], f"FarmAsyst: Your credit #{ref} agreement is ready. Log in to review and sign.")

def notify_credit_disbursed(phone, ref, amount):
    _send([phone], f"FarmAsyst: GHS {amount:.2f} from credit #{ref} has been disbursed to your account.")

def notify_officer_assigned(phone, farmer_name, farm_name):
    _send([phone], f"FarmAsyst: You have been assigned to monitor {farmer_name} ({farm_name}). Log in to view details.")

def notify_officer_visit_due(phone, farm_name, due_date):
    _send([phone], f"FarmAsyst: Scheduled visit to {farm_name} is due on {due_date}. Please log your report after the visit.")
