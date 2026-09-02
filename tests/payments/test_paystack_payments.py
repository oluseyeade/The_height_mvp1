import sys
import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.extensions import db
from app.models import Apartment, Booking, Payment
from app.services import BookingService, PaymentService
from app.seed import seed_database
from tests.conftest import clean_test_db, seed_test_apartment

class PaystackPaymentsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        clean_test_db()
        db.create_all()
        seed_database()
        seed_test_apartment()
        self.booking_service = BookingService()
        self.payment_service = PaymentService()

    def tearDown(self):
        clean_test_db()
        self.app_context.pop()

    def test_initialize_paystack_payment_pending(self):
        apt = Apartment.query.first()
        self.assertIsNotNone(apt)
        today = datetime.utcnow().date()
        check_in = today + timedelta(days=3)
        check_out = today + timedelta(days=6)

        booking, _ = self.booking_service.create_booking(
            apartment_id=apt.apartment_id,
            check_in_date=check_in,
            check_out_date=check_out,
            guest_name='Payment Tester',
            guest_email='payment@example.com',
            guest_phone='08099001122'
        )

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.headers = {'content-type': 'application/json'}
        mock_post_resp.json.return_value = {
            "status": True,
            "data": {
                "authorization_url": "https://checkout.paystack.com/mock-url",
                "reference": "PAY-THA-MOCK"
            }
        }

        with patch('requests.post', return_value=mock_post_resp):
            res, msg = self.payment_service.initialize_paystack_payment(booking.booking_ref)

        self.assertIsNotNone(res)
        self.assertTrue(res['success'])
        self.assertTrue(res['reference'].startswith('PAY-THA-'))
        self.assertEqual(res['authorization_url'], 'https://checkout.paystack.com/mock-url')

    def test_verify_paystack_payment_success_mock(self):
        apt = Apartment.query.first()
        self.assertIsNotNone(apt)
        today = datetime.utcnow().date()
        check_in = today + timedelta(days=4)
        check_out = today + timedelta(days=7)

        booking, _ = self.booking_service.create_booking(
            apartment_id=apt.apartment_id,
            check_in_date=check_in,
            check_out_date=check_out,
            guest_name='Paystack Mock Tester',
            guest_email='paystack_mock@example.com',
            guest_phone='08099001133'
        )

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.headers = {'content-type': 'application/json'}
        mock_post_resp.json.return_value = {
            "status": True,
            "data": {
                "authorization_url": "https://checkout.paystack.com/mock-url",
                "reference": "PAY-THA-MOCK2"
            }
        }

        with patch('requests.post', return_value=mock_post_resp):
            res, _ = self.payment_service.initialize_paystack_payment(booking.booking_ref)

        tx_ref = res['reference']
        total_payable = booking.total_amount
        expected_kobo = int(round(total_payable * 100))

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.headers = {'content-type': 'application/json'}
        mock_get_resp.json.return_value = {
            "status": True,
            "data": {
                "status": "success",
                "reference": tx_ref,
                "amount": expected_kobo,
                "currency": "NGN"
            }
        }

        with patch('requests.get', return_value=mock_get_resp):
            success, verified_booking, msg = self.payment_service.verify_paystack_payment(tx_ref)

        self.assertTrue(success)
        self.assertEqual(verified_booking.status, 'confirmed')
        self.assertEqual(verified_booking.payment_status, 'VERIFIED')

if __name__ == '__main__':
    unittest.main()
