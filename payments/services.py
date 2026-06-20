import uuid
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class MoMoService:
    """MTN Mobile Money API integration."""

    @property
    def BASE_URL(self):
        return settings.MOMO_BASE_URL

    @property
    def SUBSCRIPTION_KEY(self):
        return settings.MOMO_SUBSCRIPTION_KEY

    @property
    def API_USER(self):
        return settings.MOMO_API_USER

    @property
    def API_KEY(self):
        return settings.MOMO_API_KEY

    @property
    def CURRENCY(self):
        """
        MTN's sandbox only accepts EUR for test transactions — GHS is
        rejected there with INVALID_CURRENCY, even on a Ghana-market
        subscription. GHS only works once MOMO_ENVIRONMENT=production.
        """
        return 'EUR' if settings.MOMO_ENVIRONMENT == 'sandbox' else 'GHS'

    def _get_access_token(self, product='collection') -> str | None:
        """Obtain a short-lived Bearer token for the given product (collection/disbursement)."""
        import base64
        creds = base64.b64encode(f'{self.API_USER}:{self.API_KEY}'.encode()).decode()
        try:
            resp = requests.post(
                f'{self.BASE_URL}/{product}/token/',
                headers={
                    'Authorization': f'Basic {creds}',
                    'Ocp-Apim-Subscription-Key': self.SUBSCRIPTION_KEY,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json().get('access_token')
            logger.error(
                'MoMo %s token request failed: status=%s body=%s (API_USER=%r set=%s, '
                'API_KEY set=%s, SUBSCRIPTION_KEY set=%s)',
                product, resp.status_code, resp.text[:500],
                self.API_USER, bool(self.API_USER), bool(self.API_KEY), bool(self.SUBSCRIPTION_KEY),
            )
        except requests.RequestException as e:
            logger.error('MoMo %s token request raised: %s', product, e)
        return None

    def _headers(self, reference_id=None, access_token=None, product='collection', callback_url=None):
        """Build request headers, fetching a fresh access token if not provided."""
        if not access_token:
            access_token = self._get_access_token(product)
        h = {
            'X-Reference-Id': reference_id or str(uuid.uuid4()),
            'X-Target-Environment': settings.MOMO_ENVIRONMENT,
            'Ocp-Apim-Subscription-Key': self.SUBSCRIPTION_KEY,
            'Content-Type': 'application/json',
        }
        if access_token:
            h['Authorization'] = f'Bearer {access_token}'
        if callback_url:
            h['X-Callback-Url'] = callback_url
        return h

    def request_to_pay(self, amount: str, phone: str, reference: str, narration: str, callback_url: str = None) -> dict:
        """Initiate a MoMo collection (payment from buyer/farmer).

        `callback_url`, if provided, is sent as X-Callback-Url so MTN POSTs
        the final SUCCESSFUL/FAILED status to our webhook once the buyer
        approves or declines the prompt on their phone.
        """
        ref_id = str(uuid.uuid4())
        token  = self._get_access_token('collection')
        if not token:
            logger.error('MoMo request_to_pay aborted for reference=%s: no access token (see prior log line for why)', reference)
            return {
                'success': False,
                'reference_id': ref_id,
                'error': 'momo_auth_failed',
                'detail': 'Could not authenticate with MTN MoMo. Check MOMO_API_USER / MOMO_API_KEY / '
                          'MOMO_SUBSCRIPTION_KEY and see server logs for the exact MTN response.',
            }

        payload = {
            'amount': amount,
            'currency': self.CURRENCY,
            'externalId': reference,
            'payer': {'partyIdType': 'MSISDN', 'partyId': phone},
            'payerMessage': narration,
            'payeeNote': narration,
        }
        try:
            resp = requests.post(
                f'{self.BASE_URL}/collection/v1_0/requesttopay',
                json=payload,
                headers=self._headers(ref_id, token, 'collection', callback_url),
                timeout=30,
            )
            if resp.status_code == 202:
                return {'success': True, 'reference_id': ref_id, 'status_code': 202}

            logger.error('MoMo requesttopay rejected for reference=%s: status=%s body=%s',
                         reference, resp.status_code, resp.text[:500])
            return {
                'success': False,
                'reference_id': ref_id,
                'status_code': resp.status_code,
                'error': resp.text or f'MTN returned HTTP {resp.status_code}',
            }
        except requests.RequestException as e:
            logger.error('MoMo requesttopay raised for reference=%s: %s', reference, e)
            return {'success': False, 'reference_id': ref_id, 'error': str(e)}

    def transfer(self, amount: str, phone: str, reference: str, narration: str) -> dict:
        """Initiate a MoMo disbursement (payout to farmer)."""
        ref_id = str(uuid.uuid4())
        token  = self._get_access_token('disbursement')
        payload = {
            'amount': amount,
            'currency': self.CURRENCY,
            'externalId': reference,
            'payee': {'partyIdType': 'MSISDN', 'partyId': phone},
            'payerMessage': narration,
            'payeeNote': narration,
        }
        try:
            resp = requests.post(
                f'{self.BASE_URL}/disbursement/v1_0/transfer',
                json=payload,
                headers=self._headers(ref_id, token, 'disbursement'),
                timeout=30,
            )
            return {'success': resp.status_code == 202, 'reference_id': ref_id,
                    'status_code': resp.status_code}
        except requests.RequestException as e:
            return {'success': False, 'error': str(e)}

    def check_status(self, reference_id: str, operation: str = 'collection') -> dict:
        endpoint = 'collection' if operation == 'collection' else 'disbursement'
        token = self._get_access_token(endpoint)
        try:
            resp = requests.get(
                f'{self.BASE_URL}/{endpoint}/v1_0/requesttopay/{reference_id}',
                headers=self._headers(access_token=token, product=endpoint),
                timeout=30,
            )
            return {'success': True, 'data': resp.json()}
        except requests.RequestException as e:
            return {'success': False, 'error': str(e)}


class PaystackService:
    """Paystack payment integration for card/bank transfers."""

    BASE_URL = 'https://api.paystack.co'

    def _headers(self):
        return {
            'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
            'Content-Type': 'application/json',
        }

    def initialize_transaction(self, email: str, amount_ghs: float, reference: str, callback_url: str = '') -> dict:
        payload = {
            'email': email,
            'amount': int(amount_ghs * 100),  # Paystack uses pesewas
            'reference': reference,
            'currency': 'GHS',
            'callback_url': callback_url,
        }
        try:
            resp = requests.post(f'{self.BASE_URL}/transaction/initialize',
                                 json=payload, headers=self._headers(), timeout=30)
            data = resp.json()
            return {'success': data.get('status'), 'data': data.get('data', {})}
        except requests.RequestException as e:
            return {'success': False, 'error': str(e)}

    def verify_transaction(self, reference: str) -> dict:
        try:
            resp = requests.get(f'{self.BASE_URL}/transaction/verify/{reference}',
                                headers=self._headers(), timeout=30)
            data = resp.json()
            return {'success': data.get('status'), 'data': data.get('data', {})}
        except requests.RequestException as e:
            return {'success': False, 'error': str(e)}


class HubtelSMSService:
    """Hubtel SMS for Ghana-local notifications."""

    BASE_URL = 'https://smsc.hubtel.com/v1/messages/send'

    def send(self, to: str, message: str) -> dict:
        try:
            resp = requests.get(self.BASE_URL, params={
                'clientsecret': settings.HUBTEL_CLIENT_SECRET,
                'clientid': settings.HUBTEL_CLIENT_ID,
                'from': settings.HUBTEL_SENDER_ID,
                'to': to,
                'content': message,
            }, timeout=20)
            return {'success': resp.status_code == 200, 'response': resp.text}
        except requests.RequestException as e:
            return {'success': False, 'error': str(e)}


class HubtelPaymentService:
    """
    Hubtel Online Checkout — replaces Paystack for card payments.

    Uses Hubtel's documented Checkout API (payproxyapi.hubtel.com), which
    is a *separate* Hubtel product from the SMS API above and needs its
    own merchant-payment credentials (HUBTEL_PAYMENT_CLIENT_ID/SECRET +
    HUBTEL_MERCHANT_ACCOUNT_NUMBER), issued once your Hubtel merchant
    payment account is approved.

    Docs: https://businessdocs-developers.hubtel.com/docs/api-reference-online-checkout

    Note on verification: Hubtel's primary confirmation path is the
    callback webhook (POSTed to `callback_url` once payment completes),
    handled by HubtelWebhookView in views.py — mirroring how the existing
    MoMo webhook already works in this codebase. Hubtel's own docs say a
    direct status-check call is only "mandatory" as a fallback if no
    webhook has arrived after 5 minutes; that status-check endpoint isn't
    wired up yet, so `initiate_checkout` + the webhook is the supported
    path for now.
    """

    BASE_URL = 'https://payproxyapi.hubtel.com'

    def _headers(self):
        import base64
        creds = base64.b64encode(
            f'{settings.HUBTEL_PAYMENT_CLIENT_ID}:{settings.HUBTEL_PAYMENT_CLIENT_SECRET}'.encode()
        ).decode()
        return {
            'Authorization': f'Basic {creds}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def initiate_checkout(self, amount_ghs: float, description: str, client_reference: str,
                          callback_url: str, return_url: str, cancellation_url: str,
                          payee_name: str = '', payee_mobile: str = '', payee_email: str = '') -> dict:
        if not settings.HUBTEL_PAYMENT_CLIENT_ID or not settings.HUBTEL_PAYMENT_CLIENT_SECRET:
            logger.error('Hubtel checkout aborted for reference=%s: payment credentials not configured '
                        '(HUBTEL_PAYMENT_CLIENT_ID/SECRET/HUBTEL_MERCHANT_ACCOUNT_NUMBER)', client_reference)
            return {
                'success': False,
                'error': 'hubtel_payment_not_configured',
                'detail': 'Hubtel payment credentials are not set. The merchant payment account may still '
                          'be pending approval — check HUBTEL_PAYMENT_CLIENT_ID / HUBTEL_PAYMENT_CLIENT_SECRET '
                          '/ HUBTEL_MERCHANT_ACCOUNT_NUMBER.',
            }

        payload = {
            'totalAmount': float(amount_ghs),
            'description': description,
            'callbackUrl': callback_url,
            'returnUrl': return_url,
            'cancellationUrl': cancellation_url,
            'merchantAccountNumber': settings.HUBTEL_MERCHANT_ACCOUNT_NUMBER,
            'clientReference': client_reference[:32],  # Hubtel caps this at 32 chars
        }
        if payee_name:
            payload['payeeName'] = payee_name
        if payee_mobile:
            payload['payeeMobileNumber'] = payee_mobile
        if payee_email:
            payload['payeeEmail'] = payee_email

        try:
            resp = requests.post(
                f'{self.BASE_URL}/items/initiate',
                json=payload,
                headers=self._headers(),
                timeout=30,
            )
            data = resp.json() if resp.content else {}
            if resp.status_code == 200 and data.get('responseCode') == '0000':
                checkout_data = data.get('data', {})
                return {
                    'success': True,
                    'checkout_url': checkout_data.get('checkoutUrl', ''),
                    'checkout_id': checkout_data.get('checkoutId', ''),
                    'checkout_direct_url': checkout_data.get('checkoutDirectUrl', ''),
                }
            logger.error('Hubtel checkout rejected for reference=%s: status=%s body=%s',
                        client_reference, resp.status_code, resp.text[:500])
            return {
                'success': False,
                'status_code': resp.status_code,
                'error': data.get('message') or resp.text or f'Hubtel returned HTTP {resp.status_code}',
            }
        except requests.RequestException as e:
            logger.error('Hubtel checkout raised for reference=%s: %s', client_reference, e)
            return {'success': False, 'error': str(e)}


def build_momo_callback_url() -> str:
    """
    Build the X-Callback-Url MTN will POST the final payment status to.

    Uses MOMO_CALLBACK_URL if explicitly set, otherwise derives it from
    BACKEND_URL. Appends ?key=<MOMO_WEBHOOK_SECRET> when that secret is
    configured, so the webhook view can reject unauthenticated callers.
    """
    base = settings.MOMO_CALLBACK_URL or f"{settings.BACKEND_URL.rstrip('/')}/api/v1/webhooks/momo/"
    secret = getattr(settings, 'MOMO_WEBHOOK_SECRET', '')
    if secret:
        sep = '&' if '?' in base else '?'
        return f'{base}{sep}key={secret}'
    return base


def build_hubtel_callback_url() -> str:
    """Build the callbackUrl Hubtel will POST the final checkout status to."""
    return f"{settings.BACKEND_URL.rstrip('/')}/api/v1/webhooks/hubtel/"


momo_service    = MoMoService()
paystack_service = PaystackService()
sms_service     = HubtelSMSService()
hubtel_payment_service = HubtelPaymentService()
