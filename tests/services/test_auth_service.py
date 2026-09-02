import sys
import os
import unittest
import uuid

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.extensions import db
from app.models import User, Role
from app.services import UserService
from app.seed import seed_database
from tests.conftest import clean_test_db

class AuthServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        clean_test_db()
        db.create_all()
        seed_database()
        self.client = self.app.test_client()
        self.user_service = UserService()

    def tearDown(self):
        clean_test_db()
        self.app_context.pop()

    def test_roles_seeded(self):
        roles = Role.query.all()
        role_names = [r.role_name for r in roles]
        self.assertIn('Customer', role_names)
        self.assertIn('Agent', role_names)
        self.assertIn('Admin', role_names)
        self.assertIn('SuperAdmin', role_names)

    def test_superadmin_user_created(self):
        superadmin = User.query.filter_by(email='superadmin@theheightapartment.com').first()
        self.assertIsNotNone(superadmin)
        self.assertTrue(superadmin.check_password('Admin@Height2026!'))

    def test_user_registration_service(self):
        unique_email = f"cust_{uuid.uuid4().hex[:6]}@example.com"
        user, message = self.user_service.register_user(
            full_name='Test Customer',
            email=unique_email,
            phone='08012345678',
            password='Password123!',
            role_name='Customer'
        )
        self.assertIsNotNone(user)
        self.assertEqual(user.email, unique_email)
        self.assertEqual(user.role.role_name, 'Customer')

    def test_user_authentication_service(self):
        unique_email = f"auth_{uuid.uuid4().hex[:6]}@example.com"
        user, message = self.user_service.register_user(
            full_name='Auth Customer',
            email=unique_email,
            phone='08099887766',
            password='Password123!',
            role_name='Customer'
        )
        authenticated_user, auth_msg = self.user_service.authenticate(unique_email, 'Password123!')
        self.assertIsNotNone(authenticated_user)
        self.assertEqual(authenticated_user.user_id, user.user_id)

if __name__ == '__main__':
    unittest.main()
