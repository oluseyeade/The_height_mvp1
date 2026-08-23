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
from pkg.seeds.seed_roles import seed_roles_and_superadmin
from pkg.seeds.seed_apartments import seed_default_apartments
from pkg.services.dashboard_service import DashboardService
from pkg.services.report_service import ReportService

class SuperAdminAnalyticsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        seed_roles_and_superadmin()
        seed_default_apartments()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_dashboard_metrics(self):
        admin_metrics = DashboardService.get_admin_metrics()
        self.assertIn('total_bookings', admin_metrics)
        self.assertIn('total_revenue', admin_metrics)
        self.assertIn('occupancy_rate', admin_metrics)

        super_metrics = DashboardService.get_superadmin_metrics()
        self.assertIn('total_users', super_metrics)
        self.assertIn('total_agents', super_metrics)

    def test_csv_report_generation(self):
        csv_data = ReportService.generate_bookings_csv()
        self.assertTrue(csv_data.startswith('Booking Ref,Guest Name'))

    def test_admin_dashboard_routes(self):
        # Login SuperAdmin
        superadmin = User.query.filter_by(email='superadmin@theheightapartment.com').first()
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(superadmin.user_id)

        r_admin = self.client.get('/admin/')
        self.assertEqual(r_admin.status_code, 200)

        r_superadmin = self.client.get('/superadmin/')
        self.assertEqual(r_superadmin.status_code, 200)

        r_audit = self.client.get('/superadmin/audit-logs')
        self.assertEqual(r_audit.status_code, 200)

if __name__ == '__main__':
    unittest.main()
