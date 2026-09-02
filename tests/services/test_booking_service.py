import sys
import os
import unittest
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.extensions import db
from app.models import Apartment, Booking, User
from app.services import BookingService, UserService
from app.seed import seed_database
from tests.conftest import clean_test_db, seed_test_apartment

class BookingServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        clean_test_db()
        db.create_all()
        seed_database()
        seed_test_apartment()
        self.booking_service = BookingService()
        self.user_service = UserService()

    def tearDown(self):
        clean_test_db()
        self.app_context.pop()

    def test_create_booking_success(self):
        apt = Apartment.query.first()
        self.assertIsNotNone(apt)
        today = datetime.utcnow().date()
        check_in = today + timedelta(days=2)
        check_out = today + timedelta(days=5)

        booking, msg = self.booking_service.create_booking(
            apartment_id=apt.apartment_id,
            check_in_date=check_in,
            check_out_date=check_out,
            guest_name='John Tester',
            guest_email='john@example.com',
            guest_phone='08011223344',
            guest_count=2
        )

        self.assertIsNotNone(booking)
        self.assertTrue(booking.booking_ref.startswith('THA-'))
        self.assertEqual(booking.status, 'pending')
        self.assertEqual(float(booking.caution_fee), 50000.00)

    def test_booking_date_validation(self):
        apt = Apartment.query.first()
        self.assertIsNotNone(apt)
        today = datetime.utcnow().date()
        invalid_check_in = today + timedelta(days=5)
        invalid_check_out = today + timedelta(days=2)

        booking, msg = self.booking_service.create_booking(
            apartment_id=apt.apartment_id,
            check_in_date=invalid_check_in,
            check_out_date=invalid_check_out,
            guest_name='Invalid Date Tester',
            guest_email='invalid@example.com',
            guest_phone='08011223344'
        )

        self.assertIsNone(booking)
        self.assertIn('after check-in', msg.lower())

if __name__ == '__main__':
    unittest.main()
