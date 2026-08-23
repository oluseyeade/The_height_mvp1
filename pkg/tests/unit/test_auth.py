import sys
import os

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import unittest
from pkg import create_app
from pkg.extensions import db
from pkg.models.user import User, Role, RoleHierarchy
from pkg.seeds.seed_roles import seed_roles_and_superadmin
from pkg.services.user_service import UserService

class AuthTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        seed_roles_and_superadmin()
        self.client = self.app.test_client()
        self.user_service = UserService()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_roles_seeded(self):
        roles = Role.query.all()
        role_names = [r.role_name for r in roles]
        self.assertIn('User', role_names)
        self.assertIn('Agent', role_names)
        self.assertIn('Admin', role_names)
        self.assertIn('SuperAdmin', role_names)

    def test_superadmin_user_created(self):
        superadmin = User.query.filter_by(email='superadmin@theheightapartment.com').first()
        self.assertIsNotNone(superadmin)
        self.assertTrue(superadmin.is_superadmin)
        self.assertTrue(superadmin.check_password('SuperAdmin@2026'))

    def test_user_registration_service(self):
        success, message, user = self.user_service.register_user(
            full_name='Test Customer',
            email='customer@example.com',
            password='Password123!',
            phone='08012345678',
            role_name='User'
        )
        self.assertTrue(success)
        self.assertIsNotNone(user)
        self.assertEqual(user.role.hierarchy_level, RoleHierarchy.USER)

    def test_homepage_route(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'THE HEIGHT', response.data)

    def test_login_route_get(self):
        response = self.client.get('/auth/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Sign In', response.data)

if __name__ == '__main__':
    unittest.main()
