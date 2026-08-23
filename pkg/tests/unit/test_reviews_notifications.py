import sys
import os
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import unittest
from pkg import create_app
from pkg.extensions import db
from pkg.models.user import User
from pkg.models.apartment import Apartment
from pkg.models.booking import Booking
from pkg.models.review import Review
from pkg.models.notification import EmailLog, WhatsAppLog
from pkg.seeds.seed_roles import seed_roles_and_superadmin
from pkg.seeds.seed_apartments import seed_default_apartments
from pkg.services.booking_service import BookingService
from pkg.services.review_service import ReviewService
from pkg.notifications.celery_tasks import async_send_booking_received_notification

class ReviewNotificationTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        seed_roles_and_superadmin()
        seed_default_apartments()
        self.client = self.app.test_client()
        self.booking_service = BookingService()
        self.review_service = ReviewService()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_review_policy_enforcement(self):
        apt = Apartment.query.first()
        today = datetime.now().date()
        check_in = (today - timedelta(days=10)).strftime('%Y-%m-%d')
        check_out = (today - timedelta(days=5)).strftime('%Y-%m-%d')

        # 1. Create booking
        s_b, m_b, booking = self.booking_service.create_booking_request(
            apartment_id=apt.apartment_id,
            check_in_str=check_in,
            check_out_str=check_out,
            guest_name='Review Guest',
            guest_email='review@guest.com',
            guest_phone='08012345678',
            allow_past=True
        )
        self.assertTrue(s_b)

        # 2. Attempt review before completion (status='pending') -> Should FAIL
        s1, m1, r1 = self.review_service.submit_verified_review(
            booking_ref=booking.booking_ref,
            rating=5,
            title='Early Review',
            comment='Tried to review early'
        )
        self.assertFalse(s1)
        self.assertIn('completed stays', m1)

        # 3. Update status to completed/checked-out
        booking.status = 'completed'
        db.session.commit()

        # 4. Submit review on completed stay -> Should SUCCEED with Verified Guest badge
        s2, m2, r2 = self.review_service.submit_verified_review(
            booking_ref=booking.booking_ref,
            rating=5,
            title='Verified 5-Star Stay',
            comment='Outstanding luxury service and penthouse view.'
        )
        self.assertTrue(s2)
        self.assertTrue(r2.is_verified)

        # 5. Attempt second review for same booking -> Should FAIL (1 review per booking rule)
        s3, m3, r3 = self.review_service.submit_verified_review(
            booking_ref=booking.booking_ref,
            rating=4,
            title='Duplicate Review',
            comment='Duplicate attempt'
        )
        self.assertFalse(s3)
        self.assertIn('already been submitted', m3)

    def test_notification_logging(self):
        async_send_booking_received_notification(
            recipient_email='test@guest.com',
            recipient_phone='08011223344',
            booking_ref='THA-BK-TEST',
            apartment_title='Executive Suite'
        )

        email_entry = EmailLog.query.filter_by(recipient='test@guest.com').first()
        whatsapp_entry = WhatsAppLog.query.filter_by(recipient='08011223344').first()

        self.assertIsNotNone(email_entry)
        self.assertIsNotNone(whatsapp_entry)
        self.assertIn('THA-BK-TEST', email_entry.subject)

if __name__ == '__main__':
    unittest.main()
