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
from pkg.models.corporate import CorporateEnquiry, CorporateQuote
from pkg.seeds.seed_roles import seed_roles_and_superadmin
from pkg.services.corporate_service import CorporateService

class CorporateTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        seed_roles_and_superadmin()
        self.client = self.app.test_client()
        self.corp_service = CorporateService()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_corporate_enquiry_submission(self):
        today = datetime.now().date()
        check_in = (today + timedelta(days=10)).strftime('%Y-%m-%d')
        check_out = (today + timedelta(days=25)).strftime('%Y-%m-%d')

        success, message, enquiry = self.corp_service.submit_corporate_enquiry(
            company_name='Chevron Corp',
            contact_person='Executive Director',
            email='corporate@chevron.com',
            phone='08011223344',
            check_in_str=check_in,
            check_out_str=check_out,
            guest_count=5,
            suite_count=3,
            budget_range='₦5M - ₦10M',
            special_requests='Weekly VIP chauffeur and laundry'
        )

        self.assertTrue(success)
        self.assertIsNotNone(enquiry)
        self.assertEqual(enquiry.length_of_stay, 15)
        self.assertEqual(enquiry.status, 'new')

    def test_corporate_quotation_issuance(self):
        today = datetime.now().date()
        check_in = (today + timedelta(days=5)).strftime('%Y-%m-%d')
        check_out = (today + timedelta(days=15)).strftime('%Y-%m-%d')

        _, _, enquiry = self.corp_service.submit_corporate_enquiry(
            company_name='Shell Oil',
            contact_person='HR Manager',
            email='hr@shell.com',
            phone='08055667788',
            check_in_str=check_in,
            check_out_str=check_out,
            guest_count=2,
            suite_count=2
        )

        superadmin = User.query.filter_by(email='superadmin@theheightapartment.com').first()
        valid_until = (today + timedelta(days=30)).strftime('%Y-%m-%d')

        s_q, m_q, quote = self.corp_service.create_quotation(
            enquiry_id=enquiry.enquiry_id,
            amount=2000000,
            discount=200000,
            room_type='2x Penthouse Royal Suites',
            valid_until_str=valid_until,
            admin_user_id=superadmin.user_id
        )

        self.assertTrue(s_q)
        self.assertIsNotNone(quote)
        self.assertEqual(quote.final_amount, 1800000.0)
        self.assertEqual(enquiry.status, 'quoted')
        self.assertTrue(quote.quote_number.startswith('THA-CQT-'))

    def test_corporate_public_routes(self):
        r_index = self.client.get('/corporate/')
        self.assertEqual(r_index.status_code, 200)

        r_form = self.client.get('/corporate/request-quote')
        self.assertEqual(r_form.status_code, 200)

if __name__ == '__main__':
    unittest.main()
