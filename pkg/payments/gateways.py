import hashlib
import hmac
import os
import requests


class PaystackGateway:
    def __init__(self):
        self.secret_key = os.getenv('PAYSTACK_SECRET_KEY')
        self.base_url = 'https://api.paystack.co'

    def _get_headers(self):
        if not self.secret_key:
            return None
        return {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json'
        }

    def initialize_transaction(self, email, amount_kobo, reference, callback_url):
        """
        Initializes a Paystack transaction. Amount must be in kobo (₦100 = 10000 kobo).
        """
        if not self.secret_key:
            return False, 'Paystack is not configured. Set PAYSTACK_SECRET_KEY in your environment.', None

        headers = self._get_headers()
        payload = {
            'email': email,
            'amount': int(amount_kobo),
            'reference': reference,
        }
        if callback_url:
            payload['callback_url'] = callback_url

        try:
            response = requests.post(f'{self.base_url}/transaction/initialize', json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get('status'):
                return True, data['data']['authorization_url'], data['data']['reference']
            return False, data.get('message', 'Paystack initialization failed.'), None
        except requests.RequestException as exc:
            return False, f'Gateway connection error: {exc}', None
        except ValueError:
            return False, 'Paystack returned an invalid response.', None

    def verify_transaction(self, reference):
        if not self.secret_key:
            return False, 'Paystack is not configured. Set PAYSTACK_SECRET_KEY in your environment.'

        headers = {'Authorization': f'Bearer {self.secret_key}'}
        try:
            response = requests.get(f'{self.base_url}/transaction/verify/{reference}', headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get('status') and data.get('data', {}).get('status') == 'success':
                return True, data['data']
            return False, data.get('message', 'Transaction verification failed.')
        except requests.RequestException as exc:
            return False, f'Gateway verification error: {exc}'
        except ValueError:
            return False, 'Paystack returned an invalid response.'

    def verify_webhook_signature(self, payload, signature):
        if not self.secret_key:
            return False

        expected_signature = hmac.new(
            self.secret_key.encode('utf-8'),
            payload,
            hashlib.sha512
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature or '')
