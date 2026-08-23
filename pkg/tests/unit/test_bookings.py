import sys
import os
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import unittest
from pkg import create_app
from pkg.extensions import db
from pkg.models.user import User, Role, RoleHierarchy
from pkg.models.apartment import Apartment
from pkg.models.booking import Booking
from pkg.seeds.seed_roles import seed_roles_and_superadmin
from pkg.seeds.seed_apartments import seed_default_apartments
from pkg.services.booking_service import BookingService

class BookingTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        seed_roles_and_superadmin()
        seed_default_apartments()
        self.client = self.app.test_client()
        self.booking_service = BookingService()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_booking_creation_service(self):
        apt = Apartment.query.first()
        today = datetime.now().date()
        check_in = (today + timedelta(days=2)).strftime('%Y-%m-%d')
        check_out = (today + timedelta(days=5)).strftime('%Y-%m-%d')

        success, message, booking = self.booking_service.create_booking_request(
            apartment_id=apt.apartment_id,
            check_in_str=check_in,
            check_out_str=check_out,
            guest_count=2,
            guest_name='Guest Traveller',
            guest_email='guest@example.com',
            guest_phone='08099887766'
        )

        self.assertTrue(success)
        self.assertIsNotNone(booking)
        self.assertEqual(booking.total_nights, 3)
        self.assertEqual(booking.total_price, apt.price_per_night * 3)
        self.assertEqual(booking.deposit_required, 50000.0)
        self.assertTrue(booking.booking_ref.startswith('THA-BK-'))

    def test_overlapping_booking_validation(self):
        apt = Apartment.query.first()
        today = datetime.now().date()
        check_in = (today + timedelta(days=10)).strftime('%Y-%m-%d')
        check_out = (today + timedelta(days=15)).strftime('%Y-%m-%d')

        # First booking succeeds
        s1, m1, b1 = self.booking_service.create_booking_request(
            apartment_id=apt.apartment_id,
            check_in_str=check_in,
            check_out_str=check_out,
            guest_name='First Guest',
            guest_email='first@example.com',
            guest_phone='08011112222'
        )
        self.assertTrue(s1)

        # Overlapping booking fails
        overlap_in = (today + timedelta(days=12)).strftime('%Y-%m-%d')
        overlap_out = (today + timedelta(days=18)).strftime('%Y-%m-%d')

        s2, m2, b2 = self.booking_service.create_booking_request(
            apartment_id=apt.apartment_id,
            check_in_str=overlap_in,
            check_out_str=overlap_out,
            guest_name='Second Guest',
            guest_email='second@example.com',
            guest_phone='08033334444'
        )
        self.assertFalse(s2)
        self.assertIn('already reserved', m2)

    def test_fullcalendar_events_api(self):
        apt = Apartment.query.first()
        response = self.client.get(f'/availability/api/events/{apt.apartment_id}')
        self.assertEqual(response.status_code, 200)

if __name__ == '__main__':
    unittest.main()
