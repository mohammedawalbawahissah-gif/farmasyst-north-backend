"""
farmasyst_north/sms_service.py
Africa's Talking SMS service for FarmAsyst North.
Drop this file into the farmasyst_north/ directory.
"""

import logging
import africastalking
from django.conf import settings

logger = logging.getLogger(__name__)

# Initialise once
africastalking.initialize(
    username=settings.AFRICASTALKING_USERNAME,
    api_key=settings.AFRICASTALKING_API_KEY,
)
sms = africastalking.SMS


def _send(recipients: list[str], message: str) -> None:
    """
    Send an SMS to one or more recipients.
    recipients: list of E.164 numbers e.g. ['+233241597327']
    Silently logs errors so SMS failures never crash the main request.
    """
    try:
        response = sms.send(message, recipients)
        logger.info("SMS sent: %s", response)
    except Exception as exc:
        logger.error("SMS failed to %s: %s", recipients, exc)


# ── Order notifications ──────────────────────────────────────────────────────

def notify_consumer_order_placed(phone: str, order_ref: str, amount: float) -> None:
    _send([phone], f"FarmAsyst: Your order #{order_ref} of GHS {amount:.2f} has been placed. We will notify you when it ships.")


def notify_farmer_new_order(phone: str, order_ref: str, product: str, qty: float) -> None:
    _send([phone], f"FarmAsyst: New order #{order_ref} received for {qty} unit(s) of {product}. Log in to confirm.")


# ── Payment confirmations ────────────────────────────────────────────────────

def notify_payment_success(phone: str, order_ref: str, amount: float, method: str) -> None:
    _send([phone], f"FarmAsyst: Payment of GHS {amount:.2f} via {method} confirmed for order #{order_ref}. Thank you!")


def notify_payment_failed(phone: str, order_ref: str) -> None:
    _send([phone], f"FarmAsyst: Payment for order #{order_ref} was not completed. Please retry or contact support.")


# ── OTP / account verification ───────────────────────────────────────────────

def send_otp(phone: str, otp: str) -> None:
    _send([phone], f"FarmAsyst verification code: {otp}. Valid for 10 minutes. Do not share this code.")


# ── Credit application status ────────────────────────────────────────────────

def notify_credit_submitted(phone: str, ref: str) -> None:
    _send([phone], f"FarmAsyst: Your credit application #{ref} has been submitted and is under review.")


def notify_credit_under_review(phone: str, ref: str) -> None:
    _send([phone], f"FarmAsyst: Your credit application #{ref} is now under review. We will update you soon.")


def notify_credit_approved(phone: str, ref: str, amount: float) -> None:
    _send([phone], f"FarmAsyst: Congratulations! Your credit application #{ref} for GHS {amount:.2f} has been approved.")


def notify_credit_declined(phone: str, ref: str) -> None:
    _send([phone], f"FarmAsyst: Your credit application #{ref} was not approved at this time. Contact support for details.")


def notify_credit_agreement(phone: str, ref: str) -> None:
    _send([phone], f"FarmAsyst: Your credit #{ref} agreement is ready. Log in to review and sign.")


def notify_credit_disbursed(phone: str, ref: str, amount: float) -> None:
    _send([phone], f"FarmAsyst: GHS {amount:.2f} from credit #{ref} has been disbursed to your account.")


# ── Monitoring officer alerts ─────────────────────────────────────────────────

def notify_officer_assigned(phone: str, farmer_name: str, farm_name: str) -> None:
    _send([phone], f"FarmAsyst: You have been assigned to monitor {farmer_name} ({farm_name}). Log in to view details.")


def notify_officer_visit_due(phone: str, farm_name: str, due_date: str) -> None:
    _send([phone], f"FarmAsyst: Scheduled visit to {farm_name} is due on {due_date}. Please log your report after the visit.")
