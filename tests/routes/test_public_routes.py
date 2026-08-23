import sys
import os
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.extensions import db
from starter import seed_database
from tests.conftest import clean_test_db

class PublicRoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        seed_database()
        self.client = self.app.test_client()

    def tearDown(self):
        clean_test_db()
        self.app_context.pop()

    def test_homepage_route(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_health_check_route(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'healthy')

    def test_login_route_get(self):
        response = self.client.get('/auth/login')
        self.assertEqual(response.status_code, 200)

if __name__ == '__main__':
    unittest.main()
