import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import unittest
from pkg import create_app
from pkg.extensions import db
from pkg.models.user import User, Role, RoleHierarchy
from pkg.models.apartment import Category, Apartment, Facility
from pkg.seeds.seed_roles import seed_roles_and_superadmin
from pkg.seeds.seed_apartments import seed_default_apartments
from pkg.services.apartment_service import ApartmentService

class ApartmentTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        seed_roles_and_superadmin()
        seed_default_apartments()
        self.client = self.app.test_client()
        self.apt_service = ApartmentService()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_seeded_categories_and_apartments(self):
        categories = Category.query.all()
        self.assertGreaterEqual(len(categories), 4)

        apartments = Apartment.query.all()
        self.assertGreaterEqual(len(apartments), 4)

    def test_apartment_creation_service(self):
        cat = Category.query.first()
        success, message, apt = self.apt_service.create_apartment(
            title='Test Presidential Suite',
            description='Exclusive presidential luxury suite with private terrace.',
            price_per_night=250000,
            category_id=cat.category_id,
            bedrooms=4,
            bathrooms=4,
            capacity=8
        )
        self.assertTrue(success)
        self.assertEqual(apt.title, 'Test Presidential Suite')
        self.assertEqual(apt.price_per_night, 250000.0)

    def test_public_apartment_routes(self):
        response = self.client.get('/apartments/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Available Luxury Suites', response.data)

        apt = Apartment.query.first()
        response_detail = self.client.get(f'/apartments/{apt.apartment_id}')
        self.assertEqual(response_detail.status_code, 200)
        self.assertIn(apt.title.encode('utf-8'), response_detail.data)

if __name__ == '__main__':
    unittest.main()
