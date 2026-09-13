import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.extensions import db
from app.models import Apartment, Booking, Payment, Receipt, Availability
from app.services import BookingService, PaymentService
from app.seed import seed_database
from tests.conftest import clean_test_db, seed_test_apartment

class PaymentValidatedBookingTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        clean_test_db()
        db.create_all()
        seed_database(self.app)
        seed_test_apartment()
        self.client = self.app.test_client()
        self.booking_service = BookingService()
        self.payment_service = PaymentService()

    def tearDown(self):
        clean_test_db()
        self.app_context.pop()

    def test_01_fresh_temporary_reservation(self):
        apt = Apartment.query.first()
        today = datetime.utcnow().date()
        check_in = today + timedelta(days=2)
        check_out = today + timedelta(days=5)

        booking, msg = self.booking_service.create_booking(
            apartment_id=apt.apartment_id,
            check_in_date=check_in,
            check_out_date=check_out,
            guest_name='Temp Tester',
            guest_email='temp@example.com',
            guest_phone='08011223344',
            guest_count=2
        )

        self.assertIsNotNone(booking)
        self.assertEqual(booking.status, 'pending')
        self.assertEqual(booking.payment_status, 'PENDING_PAYMENT')

    def test_02_stale_temporary_reservation_expiration(self):
        apt = Apartment.query.first()
        today = datetime.utcnow().date()
        check_in = today + timedelta(days=10)
        check_out = today + timedelta(days=12)

        booking, msg = self.booking_service.create_booking(
            apartment_id=apt.apartment_id,
            check_in_date=check_in,
            check_out_date=check_out,
            guest_name='Stale Tester',
            guest_email='stale@example.com',
            guest_phone='08011223344'
        )
        
        booking.created_at = datetime.utcnow() - timedelta(minutes=35)
        db.session.commit()

        self.booking_service.expire_stale_pending_bookings(timeout_minutes=30)
        
        updated = Booking.query.get(booking.booking_id)
        self.assertEqual(updated.status, 'EXPIRED')
        self.assertEqual(updated.payment_status, 'TIMED_OUT')

    @patch('app.services.requests.get')
    def test_03_failed_paystack_payment(self, mock_get):
        apt = Apartment.query.first()
        today = datetime.utcnow().date()
        booking, msg = self.booking_service.create_booking(
            apartment_id=apt.apartment_id,
            check_in_date=today + timedelta(days=15),
            check_out_date=today + timedelta(days=18),
            guest_name='Fail Tester',
            guest_email='fail@example.com',
            guest_phone='08011223344'
        )
        
        payment = Payment(
            booking_id=booking.booking_id,
            amount=booking.total_amount or (float(booking.final_amount) + float(booking.caution_fee)),
            payment_method='paystack',
            transaction_ref='TX-FAIL-REF-001',
            paystack_reference='TX-FAIL-REF-001',
            status='pending'
        )
        db.session.add(payment)
        db.session.commit()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'status': False,
            'message': 'Transaction failed or declined.',
            'data': {'status': 'failed', 'amount': 100000, 'currency': 'NGN'}
        }
        mock_get.return_value = mock_resp

        success, b, err_msg = self.payment_service.verify_paystack_payment('TX-FAIL-REF-001')
        self.assertFalse(success)
        self.assertEqual(b.status, 'EXPIRED')
        self.assertEqual(b.payment_status, 'PAYMENT_FAILED')

    @patch('app.services.requests.get')
    def test_04_successful_paystack_verification(self, mock_get):
        apt = Apartment.query.first()
        today = datetime.utcnow().date()
        check_in = today + timedelta(days=20)
        check_out = today + timedelta(days=22)

        booking, msg = self.booking_service.create_booking(
            apartment_id=apt.apartment_id,
            check_in_date=check_in,
            check_out_date=check_out,
            guest_name='Success Tester',
            guest_email='success@example.com',
            guest_phone='08011223344'
        )
        
        expected_total = float(booking.final_amount) + float(booking.caution_fee)
        expected_kobo = int(round(expected_total * 100))

        payment = Payment(
            booking_id=booking.booking_id,
            amount=expected_total,
            payment_method='paystack',
            transaction_ref='TX-SUCCESS-REF-001',
            paystack_reference='TX-SUCCESS-REF-001',
            status='pending'
        )
        db.session.add(payment)
        db.session.commit()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'status': True,
            'message': 'Verification successful',
            'data': {
                'status': 'success',
                'amount': expected_kobo,
                'currency': 'NGN',
                'reference': 'TX-SUCCESS-REF-001'
            }
        }
        mock_get.return_value = mock_resp

        success, b, msg = self.payment_service.verify_paystack_payment('TX-SUCCESS-REF-001')
        self.assertTrue(success)
        self.assertEqual(b.status, 'confirmed')
        self.assertEqual(b.payment_status, 'VERIFIED')
        self.assertEqual(b.payments[0].status, 'verified')

    @patch('app.services.requests.get')
    def test_05_incorrect_amount(self, mock_get):
        apt = Apartment.query.first()
        today = datetime.utcnow().date()
        booking, msg = self.booking_service.create_booking(
            apartment_id=apt.apartment_id,
            check_in_date=today + timedelta(days=25),
            check_out_date=today + timedelta(days=27),
            guest_name='Wrong Amount Tester',
            guest_email='wrongamt@example.com',
            guest_phone='08011223344'
        )

        payment = Payment(
            booking_id=booking.booking_id,
            amount=100000.00,
            payment_method='paystack',
            transaction_ref='TX-WRONG-AMT-001',
            paystack_reference='TX-WRONG-AMT-001',
            status='pending'
        )
        db.session.add(payment)
        db.session.commit()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'status': True,
            'data': {'status': 'success', 'amount': 500, 'currency': 'NGN'}
        }
        mock_get.return_value = mock_resp

        success, b, msg = self.payment_service.verify_paystack_payment('TX-WRONG-AMT-001')
        self.assertFalse(success)
        self.assertNotEqual(b.status, 'confirmed')

    @patch('app.services.requests.get')
    def test_06_incorrect_currency(self, mock_get):
        apt = Apartment.query.first()
        today = datetime.utcnow().date()
        booking, msg = self.booking_service.create_booking(
            apartment_id=apt.apartment_id,
            check_in_date=today + timedelta(days=30),
            check_out_date=today + timedelta(days=32),
            guest_name='USD Tester',
            guest_email='usd@example.com',
            guest_phone='08011223344'
        )

        payment = Payment(
            booking_id=booking.booking_id,
            amount=100000.00,
            payment_method='paystack',
            transaction_ref='TX-USD-REF-001',
            paystack_reference='TX-USD-REF-001',
            status='pending'
        )
        db.session.add(payment)
        db.session.commit()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'status': True,
            'data': {'status': 'success', 'amount': 10000000, 'currency': 'USD'}
        }
        mock_get.return_value = mock_resp

        success, b, msg = self.payment_service.verify_paystack_payment('TX-USD-REF-001')
        self.assertFalse(success)
        self.assertNotEqual(b.status, 'confirmed')

    def test_07_incorrect_payment_reference(self):
        success, b, msg = self.payment_service.verify_paystack_payment('NON-EXISTENT-REF-999')
        self.assertFalse(success)
        self.assertIsNone(b)

    @patch('app.services.requests.get')
    def test_08_callback_and_webhook_idempotency(self, mock_get):
        apt = Apartment.query.first()
        today = datetime.utcnow().date()
        booking, msg = self.booking_service.create_booking(
            apartment_id=apt.apartment_id,
            check_in_date=today + timedelta(days=35),
            check_out_date=today + timedelta(days=37),
            guest_name='Idempotent Tester',
            guest_email='idempotent@example.com',
            guest_phone='08011223344'
        )
        expected_total = float(booking.final_amount) + float(booking.caution_fee)
        expected_kobo = int(round(expected_total * 100))

        payment = Payment(
            booking_id=booking.booking_id,
            amount=expected_total,
            payment_method='paystack',
            transaction_ref='TX-IDEM-001',
            paystack_reference='TX-IDEM-001',
            status='pending'
        )
        db.session.add(payment)
        db.session.commit()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'status': True,
            'data': {'status': 'success', 'amount': expected_kobo, 'currency': 'NGN', 'reference': 'TX-IDEM-001'}
        }
        mock_get.return_value = mock_resp

        s1, b1, m1 = self.payment_service.verify_paystack_payment('TX-IDEM-001')
        self.assertTrue(s1)

        s2, b2, m2 = self.payment_service.verify_paystack_payment('TX-IDEM-001')
        self.assertTrue(s2)

        payments_count = Payment.query.filter_by(booking_id=booking.booking_id).count()
        receipts_count = Receipt.query.filter_by(payment_id=payment.payment_id).count()
        self.assertEqual(payments_count, 1)
        self.assertEqual(receipts_count, 1)

    @patch('app.services.requests.get')
    def test_09_repeated_verification(self, mock_get):
        apt = Apartment.query.first()
        today = datetime.utcnow().date()
        booking, _ = self.booking_service.create_booking(
            apartment_id=apt.apartment_id,
            check_in_date=today + timedelta(days=40),
            check_out_date=today + timedelta(days=42),
            guest_name='Repeat Tester',
            guest_email='repeat@example.com',
            guest_phone='08011223344'
        )
        expected_total = float(booking.final_amount) + float(booking.caution_fee)
        payment = Payment(
            booking_id=booking.booking_id,
            amount=expected_total,
            payment_method='paystack',
            transaction_ref='TX-REPEAT-001',
            paystack_reference='TX-REPEAT-001',
            status='pending'
        )
        db.session.add(payment)
        db.session.commit()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'status': True,
            'data': {'status': 'success', 'amount': int(round(expected_total * 100)), 'currency': 'NGN'}
        }
        mock_get.return_value = mock_resp

        for _ in range(3):
            s, b, m = self.payment_service.verify_paystack_payment('TX-REPEAT-001')
            self.assertTrue(s)

    def test_10_confirmed_booking_expiration_protection(self):
        apt = Apartment.query.first()
        today = datetime.utcnow().date()
        booking, _ = self.booking_service.create_booking(
            apartment_id=apt.apartment_id,
            check_in_date=today + timedelta(days=45),
            check_out_date=today + timedelta(days=47),
            guest_name='Confirmed Expiration Tester',
            guest_email='confexp@example.com',
            guest_phone='08011223344'
        )
        booking.status = 'confirmed'
        booking.payment_status = 'VERIFIED'
        booking.created_at = datetime.utcnow() - timedelta(days=10)
        db.session.commit()

        self.booking_service.expire_stale_pending_bookings(timeout_minutes=30)
        
        updated = Booking.query.get(booking.booking_id)
        self.assertEqual(updated.status, 'confirmed')
        self.assertEqual(updated.payment_status, 'VERIFIED')

    def test_11_inventory_release(self):
        apt = Apartment.query.first()
        today = datetime.utcnow().date()
        cin = today + timedelta(days=50)
        cout = today + timedelta(days=52)

        booking, _ = self.booking_service.create_booking(
            apartment_id=apt.apartment_id,
            check_in_date=cin,
            check_out_date=cout,
            guest_name='Inventory Tester',
            guest_email='inv@example.com',
            guest_phone='08011223344'
        )
        
        booking.created_at = datetime.utcnow() - timedelta(minutes=45)
        db.session.commit()
        self.booking_service.expire_stale_pending_bookings()

        new_booking, msg = self.booking_service.create_booking(
            apartment_id=apt.apartment_id,
            check_in_date=cin,
            check_out_date=cout,
            guest_name='New Inv Tester',
            guest_email='newinv@example.com',
            guest_phone='08099887766'
        )
        self.assertIsNotNone(new_booking)
        self.assertEqual(new_booking.status, 'pending')

    def test_12_double_booking_protection(self):
        apt = Apartment.query.first()
        today = datetime.utcnow().date()
        cin = today + timedelta(days=60)
        cout = today + timedelta(days=62)

        b1, _ = self.booking_service.create_booking(
            apartment_id=apt.apartment_id,
            check_in_date=cin,
            check_out_date=cout,
            guest_name='Double 1',
            guest_email='d1@example.com',
            guest_phone='08011111111'
        )
        b1.status = 'confirmed'
        b1.payment_status = 'VERIFIED'
        db.session.commit()

        b2, msg = self.booking_service.create_booking(
            apartment_id=apt.apartment_id,
            check_in_date=cin,
            check_out_date=cout,
            guest_name='Double 2',
            guest_email='d2@example.com',
            guest_phone='08022222222'
        )
        if b2:
            self.assertNotEqual(b2.apartment_id, b1.apartment_id)

    def test_13_success_route_protection(self):
        apt = Apartment.query.first()
        today = datetime.utcnow().date()
        booking, _ = self.booking_service.create_booking(
            apartment_id=apt.apartment_id,
            check_in_date=today + timedelta(days=70),
            check_out_date=today + timedelta(days=72),
            guest_name='Guard Tester',
            guest_email='guard@example.com',
            guest_phone='08011223344'
        )
        
        resp = self.client.get(f'/bookings/success/{booking.booking_ref}')
        self.assertEqual(resp.status_code, 302)
        self.assertIn(f'/bookings/detail/{booking.booking_ref}', resp.location)

    @patch('app.services.requests.get')
    def test_14_payment_expiration_race(self, mock_get):
        apt = Apartment.query.first()
        today = datetime.utcnow().date()
        booking, _ = self.booking_service.create_booking(
            apartment_id=apt.apartment_id,
            check_in_date=today + timedelta(days=80),
            check_out_date=today + timedelta(days=82),
            guest_name='Race Tester',
            guest_email='race@example.com',
            guest_phone='08011223344'
        )

        expected_total = float(booking.final_amount) + float(booking.caution_fee)
        payment = Payment(
            booking_id=booking.booking_id,
            amount=expected_total,
            payment_method='paystack',
            transaction_ref='TX-RACE-001',
            paystack_reference='TX-RACE-001',
            status='pending'
        )
        db.session.add(payment)
        db.session.commit()

        booking.status = 'EXPIRED'
        booking.payment_status = 'TIMED_OUT'
        db.session.commit()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'status': True,
            'data': {'status': 'success', 'amount': int(round(expected_total * 100)), 'currency': 'NGN'}
        }
        mock_get.return_value = mock_resp

        success, b, msg = self.payment_service.verify_paystack_payment('TX-RACE-001')
        self.assertTrue(success)
        self.assertEqual(b.status, 'confirmed')
        self.assertEqual(b.payment_status, 'VERIFIED')

if __name__ == '__main__':
    unittest.main()
