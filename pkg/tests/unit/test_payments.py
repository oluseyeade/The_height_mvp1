import json
import sys
import os
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import unittest
from unittest.mock import patch
from pkg import create_app
from pkg.extensions import db
from pkg.models.user import User
from pkg.models.apartment import Apartment
from pkg.models.booking import Booking
from pkg.models.payment import Payment
from pkg.seeds.seed_roles import seed_roles_and_superadmin
from pkg.seeds.seed_apartments import seed_default_apartments
from pkg.services.booking_service import BookingService
from pkg.services.payment_service import PaymentService

class PaymentTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        seed_roles_and_superadmin()
        seed_default_apartments()
        self.client = self.app.test_client()
        self.booking_service = BookingService()
        self.payment_service = PaymentService()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_payment_verification_and_receipt_pdf(self):
        apt = Apartment.query.first()
        today = datetime.now().date()
        check_in = (today + timedelta(days=3)).strftime('%Y-%m-%d')
        check_out = (today + timedelta(days=6)).strftime('%Y-%m-%d')

        # 1. Create Booking
        _, _, booking = self.booking_service.create_booking_request(
            apartment_id=apt.apartment_id,
            check_in_str=check_in,
            check_out_str=check_out,
            guest_name='Payment Tester',
            guest_email='tester@example.com',
            guest_phone='08011223344'
        )

        # 2. Create Payment record
        payment = Payment(
            booking_id=booking.booking_id,
            amount=50000.0,
            payment_method='bank_transfer',
            transaction_ref=f"BT-{booking.booking_ref}",
            status='pending'
        )
        db.session.add(payment)
        db.session.commit()

        # 3. Admin verifies payment
        superadmin = User.query.filter_by(email='superadmin@theheightapartment.com').first()
        success, message, receipt = self.payment_service.verify_payment_and_generate_receipt(
            payment_id=payment.payment_id,
            admin_user_id=superadmin.user_id
        )

        self.assertTrue(success)
        self.assertIsNotNone(receipt)
        self.assertTrue(receipt.receipt_number.startswith('THA-RCT-'))
        self.assertEqual(booking.status, 'confirmed')

        # Check PDF file existence
        abs_pdf_path = os.path.join(self.app.config['UPLOAD_FOLDER'], 'receipts', 'pdf', f"{receipt.receipt_number}.pdf")
        self.assertTrue(os.path.exists(abs_pdf_path))

    def test_paystack_initialization_and_callback_verification(self):
        apt = Apartment.query.first()
        today = datetime.now().date()
        check_in = (today + timedelta(days=5)).strftime('%Y-%m-%d')
        check_out = (today + timedelta(days=8)).strftime('%Y-%m-%d')

        _, _, booking = self.booking_service.create_booking_request(
            apartment_id=apt.apartment_id,
            check_in_str=check_in,
            check_out_str=check_out,
            guest_name='Paystack Tester',
            guest_email='paystack@example.com',
            guest_phone='08022334455'
        )

        with patch('pkg.services.payment_service.PaystackGateway.initialize_transaction', return_value=(True, 'https://paystack.test/checkout', 'PS-TEST-001')):
            success, message, payment = self.payment_service.initialize_paystack_payment(
                booking_ref=booking.booking_ref,
                amount=50000.0,
                user_id=None,
                transaction_ref='PS-TEST-001'
            )

        self.assertTrue(success)
        self.assertEqual(payment.payment_method, 'paystack')
        self.assertEqual(payment.status, 'pending')

        with patch('pkg.services.payment_service.PaystackGateway.verify_transaction', return_value=(True, {'status': 'success', 'reference': 'PS-TEST-001', 'amount': 5000000, 'currency': 'NGN'})):
            success, message, receipt = self.payment_service.verify_paystack_payment('PS-TEST-001')

        self.assertTrue(success)
        verified_payment = Payment.query.get(payment.payment_id)
        self.assertEqual(verified_payment.status, 'verified')
        self.assertEqual(Booking.query.get(booking.booking_id).status, 'confirmed')
        self.assertIsNotNone(receipt)

    def test_paystack_callback_uses_configured_callback_base(self):
        apt = Apartment.query.first()
        today = datetime.now().date()
        check_in = (today + timedelta(days=9)).strftime('%Y-%m-%d')
        check_out = (today + timedelta(days=12)).strftime('%Y-%m-%d')

        _, _, booking = self.booking_service.create_booking_request(
            apartment_id=apt.apartment_id,
            check_in_str=check_in,
            check_out_str=check_out,
            guest_name='Callback Tester',
            guest_email='callback@example.com',
            guest_phone='08022334466'
        )

        self.app.config['PAYSTACK_CALLBACK_URL'] = 'http://localhost:5050/payments/paystack/callback'

        with patch('pkg.services.payment_service.PaystackGateway.initialize_transaction', return_value=(True, 'https://paystack.test/checkout', 'PS-TEST-002')) as mock_init:
            self.payment_service.initialize_paystack_payment(
                booking_ref=booking.booking_ref,
                amount=50000.0,
                user_id=None,
                transaction_ref='PS-TEST-002'
            )

        callback_url = mock_init.call_args.kwargs['callback_url']
        self.assertEqual(callback_url, 'http://localhost:5050/payments/paystack/callback/PS-TEST-002')

    def test_failed_paystack_verification_keeps_booking_pending(self):
        apt = Apartment.query.first()
        today = datetime.now().date()
        check_in = (today + timedelta(days=13)).strftime('%Y-%m-%d')
        check_out = (today + timedelta(days=16)).strftime('%Y-%m-%d')

        _, _, booking = self.booking_service.create_booking_request(
            apartment_id=apt.apartment_id,
            check_in_str=check_in,
            check_out_str=check_out,
            guest_name='Failed Tester',
            guest_email='failed@example.com',
            guest_phone='08022334477'
        )

        with patch('pkg.services.payment_service.PaystackGateway.initialize_transaction', return_value=(True, 'https://paystack.test/checkout', 'PS-TEST-003')):
            self.payment_service.initialize_paystack_payment(
                booking_ref=booking.booking_ref,
                amount=50000.0,
                user_id=None,
                transaction_ref='PS-TEST-003'
            )

        with patch('pkg.services.payment_service.PaystackGateway.verify_transaction', return_value=(False, {'message': 'Transaction was not successful'})):
            success, message, receipt = self.payment_service.verify_paystack_payment('PS-TEST-003')

        self.assertFalse(success)
        self.assertIsNone(receipt)
        self.assertEqual(Booking.query.get(booking.booking_id).status, 'pending')

    def test_amount_mismatch_rejected(self):
        apt = Apartment.query.first()
        today = datetime.now().date()
        check_in = (today + timedelta(days=17)).strftime('%Y-%m-%d')
        check_out = (today + timedelta(days=20)).strftime('%Y-%m-%d')

        _, _, booking = self.booking_service.create_booking_request(
            apartment_id=apt.apartment_id,
            check_in_str=check_in,
            check_out_str=check_out,
            guest_name='Mismatch Tester',
            guest_email='mismatch@example.com',
            guest_phone='08022334488'
        )

        with patch('pkg.services.payment_service.PaystackGateway.initialize_transaction', return_value=(True, 'https://paystack.test/checkout', 'PS-TEST-004')):
            self.payment_service.initialize_paystack_payment(
                booking_ref=booking.booking_ref,
                amount=50000.0,
                user_id=None,
                transaction_ref='PS-TEST-004'
            )

        with patch('pkg.services.payment_service.PaystackGateway.verify_transaction', return_value=(True, {'status': 'success', 'reference': 'PS-TEST-004', 'amount': 3000000, 'currency': 'NGN'})):
            success, message, receipt = self.payment_service.verify_paystack_payment('PS-TEST-004')

        self.assertFalse(success)
        self.assertIn('amount', message.lower())
        self.assertEqual(Booking.query.get(booking.booking_id).status, 'pending')

    def test_duplicate_webhook_processing_is_idempotent(self):
        apt = Apartment.query.first()
        today = datetime.now().date()
        check_in = (today + timedelta(days=21)).strftime('%Y-%m-%d')
        check_out = (today + timedelta(days=24)).strftime('%Y-%m-%d')

        _, _, booking = self.booking_service.create_booking_request(
            apartment_id=apt.apartment_id,
            check_in_str=check_in,
            check_out_str=check_out,
            guest_name='Webhook Tester',
            guest_email='webhook@example.com',
            guest_phone='08022334499'
        )

        with patch('pkg.services.payment_service.PaystackGateway.initialize_transaction', return_value=(True, 'https://paystack.test/checkout', 'PS-TEST-005')):
            self.payment_service.initialize_paystack_payment(
                booking_ref=booking.booking_ref,
                amount=50000.0,
                user_id=None,
                transaction_ref='PS-TEST-005'
            )

        payload = json.dumps({'data': {'reference': 'PS-TEST-005', 'status': 'success', 'amount': 5000000, 'currency': 'NGN'}}).encode('utf-8')
        with patch('pkg.services.payment_service.PaystackGateway.verify_webhook_signature', return_value=True):
            success, message, receipt = self.payment_service.process_paystack_webhook(payload, 'sig')
        self.assertTrue(success)
        with patch('pkg.services.payment_service.PaystackGateway.verify_webhook_signature', return_value=True):
            success_again, message_again, receipt_again = self.payment_service.process_paystack_webhook(payload, 'sig')
        self.assertTrue(success_again)
        self.assertIn('already', message_again.lower())

if __name__ == '__main__':
    unittest.main()
