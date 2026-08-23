import sys
import os
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.extensions import db
from app.models import Apartment, Category
from app.services import ApartmentService
from starter import seed_database
from tests.conftest import clean_test_db, seed_test_apartment

class ApartmentServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        clean_test_db()
        db.create_all()
        seed_database()
        seed_test_apartment()
        self.apt_service = ApartmentService()

    def tearDown(self):
        clean_test_db()
        self.app_context.pop()

    def test_get_all_active_apartments(self):
        apartments = self.apt_service.get_all_active_apartments()
        self.assertGreater(len(apartments), 0)

    def test_get_featured_apartments(self):
        featured = self.apt_service.get_featured_apartments(limit=4)
        self.assertLessEqual(len(featured), 4)

    def test_category_showcase(self):
        showcase = self.apt_service.get_category_showcase()
        self.assertIsInstance(showcase, list)

    def test_update_apartment_price(self):
        apt = Apartment.query.first()
        self.assertIsNotNone(apt)
        updated_apt, msg = self.apt_service.update_apartment_price(apt.apartment_id, 200000.00)
        self.assertIsNotNone(updated_apt)
        self.assertEqual(float(updated_apt.price_per_night), 200000.00)

if __name__ == '__main__':
    unittest.main()
