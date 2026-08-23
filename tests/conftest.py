import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.extensions import db

def clean_test_db():
    try:
        db.session.rollback()
        db.session.close()
        db.session.execute(db.text("PRAGMA foreign_keys = OFF;"))
        for table in db.metadata.tables.values():
            db.session.execute(db.text(f"DELETE FROM {table.name};"))
        db.session.commit()
    except Exception as e:
        db.session.rollback()

def seed_test_apartment():
    from app.models import Category, Apartment
    cat = Category.query.first()
    if not cat:
        cat = Category(name='Test Suite Category', description='Test Category Description', is_active=True)
        db.session.add(cat)
        db.session.commit()
    apt = Apartment.query.first()
    if not apt:
        apt = Apartment(
            category_id=cat.category_id,
            title='Test Executive Suite Unit 101',
            description='Test Executive Suite Description',
            price_per_night=100000.00,
            status='available'
        )
        db.session.add(apt)
        db.session.commit()
    return apt
