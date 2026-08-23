import sys
import os
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import unittest
from pkg import create_app
from pkg.extensions import db
from pkg.models.user import User, Agent
from pkg.models.apartment import Apartment
from pkg.seeds.seed_roles import seed_roles_and_superadmin
from pkg.seeds.seed_apartments import seed_default_apartments
from pkg.services.agent_service import AgentService
from pkg.services.booking_service import BookingService

class AgentTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        seed_roles_and_superadmin()
        seed_default_apartments()
        self.client = self.app.test_client()
        self.agent_service = AgentService()
        self.booking_service = BookingService()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_agent_registration(self):
        success, message, agent = self.agent_service.register_agent(
            full_name='Test Partner Agent',
            email='agent@partner.com',
            password='AgentPassword123!',
            phone='08012345678',
            bank_name='GTBank',
            account_number='0123456789',
            account_holder_name='Test Partner Agent'
        )

        self.assertTrue(success)
        self.assertIsNotNone(agent)
        self.assertTrue(agent.agent_code.startswith('THA-AGT-'))
        self.assertEqual(agent.user.role.role_name, 'Agent')

    def test_agent_commission_award_and_payout(self):
        # 1. Register Agent
        _, _, agent = self.agent_service.register_agent(
            full_name='Referral Agent',
            email='referral@agency.com',
            password='Password123!',
            phone='08099998888',
            bank_name='Zenith Bank',
            account_number='1010101010',
            account_holder_name='Referral Agent'
        )

        # 2. Create Booking referred by agent
        apt = Apartment.query.first()
        today = datetime.now().date()
        check_in = (today + timedelta(days=2)).strftime('%Y-%m-%d')
        check_out = (today + timedelta(days=5)).strftime('%Y-%m-%d')

        _, _, booking = self.booking_service.create_booking_request(
            apartment_id=apt.apartment_id,
            check_in_str=check_in,
            check_out_str=check_out,
            agent_id=agent.agent_id,
            guest_name='Referred Guest',
            guest_email='referred@guest.com',
            guest_phone='08077776666'
        )

        # 3. Confirm booking status to trigger commission
        booking.status = 'confirmed'
        comm = self.agent_service.calculate_and_award_commission(booking)

        self.assertIsNotNone(comm)
        expected_commission = (booking.final_amount * 5.0) / 100.0
        self.assertEqual(comm.commission_amount, expected_commission)

        # 4. Mark commission paid
        superadmin = User.query.filter_by(email='superadmin@theheightapartment.com').first()
        s_p, m_p = self.agent_service.mark_commission_paid(
            commission_id=comm.commission_id,
            payment_reference='PAYOUT-REF-101',
            admin_user_id=superadmin.user_id
        )

        self.assertTrue(s_p)
        self.assertEqual(comm.status, 'paid')
        self.assertEqual(agent.total_earnings, expected_commission)

    def test_verified_agent_referral_discount_is_applied_only_for_active_agent_code(self):
        _, _, agent = self.agent_service.register_agent(
            full_name='Referral Agent Two',
            email='referral-two@agency.com',
            password='Password123!',
            phone='08088887777',
            bank_name='First Bank',
            account_number='2222222222',
            account_holder_name='Referral Agent Two'
        )

        apt = Apartment.query.first()
        today = datetime.now().date()
        check_in = (today + timedelta(days=3)).strftime('%Y-%m-%d')
        check_out = (today + timedelta(days=6)).strftime('%Y-%m-%d')

        success, message, booking = self.booking_service.create_booking_request(
            apartment_id=apt.apartment_id,
            check_in_str=check_in,
            check_out_str=check_out,
            guest_name='Discount Guest',
            guest_email='discount@guest.com',
            guest_phone='08012344321',
            referral_code=agent.agent_code
        )

        self.assertTrue(success)
        self.assertEqual(booking.agent_id, agent.agent_id)
        self.assertEqual(booking.discount_amount, booking.total_price * 0.03)
        self.assertEqual(booking.final_amount, booking.total_price - booking.discount_amount)

    def test_agent_registration_route(self):
        response = self.client.get('/agent/register')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Partner Agent Registration', response.data)

if __name__ == '__main__':
    unittest.main()
