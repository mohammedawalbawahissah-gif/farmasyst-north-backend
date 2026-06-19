import uuid
import requests
from django.conf import settings


class MoMoService:
    """MTN Mobile Money API integration."""

    BASE_URL = settings.MOMO_BASE_URL
    SUBSCRIPTION_KEY = settings.MOMO_SUBSCRIPTION_KEY
    API_USER = settings.MOMO_API_USER
    API_KEY  = settings.MOMO_API_KEY

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
        except Exception:
            pass
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
        payload = {
            'amount': amount,
            'currency': 'GHS',
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
            return {'success': resp.status_code == 202, 'reference_id': ref_id,
                    'status_code': resp.status_code, 'response': resp.text}
        except requests.RequestException as e:
            return {'success': False, 'error': str(e)}

    def transfer(self, amount: str, phone: str, reference: str, narration: str) -> dict:
        """Initiate a MoMo disbursement (payout to farmer)."""
        ref_id = str(uuid.uuid4())
        token  = self._get_access_token('disbursement')
        payload = {
            'amount': amount,
            'currency': 'GHS',
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


momo_service    = MoMoService()
paystack_service = PaystackService()
sms_service     = HubtelSMSService()
