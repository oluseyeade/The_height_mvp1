import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

from app import create_app
from app.extensions import db
from app.models import Role, User, SuperAdmin, Admin, Category, Apartment, Facility, Amenity

app = create_app(os.getenv('FLASK_ENV', 'development'))

def seed_database(app_instance=None):
    from flask import has_app_context
    ctx = None
    if not has_app_context():
        target_app = app_instance or app
        ctx = target_app.app_context()
        ctx.push()

    try:
        db.create_all()
        print("[OK] Database tables created successfully.")

        # Seed System Roles
        roles_data = [
            ('SuperAdmin', 'Platform Super Administrator with complete override capabilities', 4, True),
            ('Admin', 'Apartments and Reservations Manager', 3, False),
            ('Agent', 'Accredited Booking Referral Agent', 2, False),
            ('Customer', 'Registered Guest / Customer', 1, False)
        ]

        for r_name, desc, level, can_override in roles_data:
            existing_role = Role.query.filter_by(role_name=r_name).first()
            if not existing_role:
                role = Role(role_name=r_name, description=desc, hierarchy_level=level, can_override=can_override)
                db.session.add(role)
        db.session.commit()
        print("[OK] System Roles seeded.")

        # Seed Default SuperAdmin Account
        superadmin_role = Role.query.filter_by(role_name='SuperAdmin').first()
        super_user = User.query.filter_by(email='superadmin@theheightapartment.com').first()
        if not super_user:
            super_user = User(
                full_name='Super Administrator',
                email='superadmin@theheightapartment.com',
                phone='+2348000000000',
                role_id=superadmin_role.role_id,
                status='active'
            )
            super_user.set_password('Admin@Height2026!')
            db.session.add(super_user)
            db.session.flush()

            sa_profile = SuperAdmin(user_id=super_user.user_id)
            db.session.add(sa_profile)
            db.session.commit()
            print("[OK] Default SuperAdmin account created (superadmin@theheightapartment.com).")

        # Seed Default Operations Admin Account
        admin_role = Role.query.filter_by(role_name='Admin').first()
        admin_user = User.query.filter_by(email='admin@theheightapartment.com').first()
        if not admin_user:
            admin_user = User(
                full_name='Operations Admin',
                email='admin@theheightapartment.com',
                phone='+2348000000001',
                role_id=admin_role.role_id,
                status='active'
            )
            admin_user.set_password('Admin@Height2026!')
            db.session.add(admin_user)
            db.session.flush()

            admin_profile = Admin(user_id=admin_user.user_id)
            db.session.add(admin_profile)
            db.session.commit()
            print("[OK] Default Operations Admin account created (admin@theheightapartment.com).")

        # Seed Categories
        categories_data = [
            ('3-Bedrooms', 'Spacious 3-bedroom luxury suites'),
            ('2-Bedrooms', 'Modern and well-furnished 2-bedroom apartments'),
            ('1-Bedroom', 'Tastefully finished 1-bedroom apartments'),
            ('Studio Apartment', 'Cozy modern studio apartment for executive stays')
        ]

        for cat_name, desc in categories_data:
            cat = Category.query.filter_by(name=cat_name).first()
            if not cat:
                db.session.add(Category(name=cat_name, description=desc))
        db.session.commit()
        print("[OK] Categories seeded.")

        # Seed Sample Apartments
        if Apartment.query.count() == 0:
            cat_3bed = Category.query.filter_by(name='3-Bedrooms').first()
            cat_2bed = Category.query.filter_by(name='2-Bedrooms').first()
            cat_1bed = Category.query.filter_by(name='1-Bedroom').first()
            cat_studio = Category.query.filter_by(name='Studio Apartment').first()

            apt1 = Apartment(
                title='3-Bedrooms Premium Apartment (Unit 1)',
                description='Panoramic city views, private terrace, jacuzzi & king-size master suite with 24/7 power guarantee & fiber Wi-Fi.',
                price_per_night=180000.00,
                bedrooms=3,
                bathrooms=3,
                category_id=cat_3bed.category_id,
                is_featured=True,
                status='available'
            )
            apt1_unit2 = Apartment(
                title='3-Bedrooms Executive Suite (Unit 2)',
                description='Panoramic city views, private terrace, jacuzzi & king-size master suite with 24/7 power guarantee & fiber Wi-Fi.',
                price_per_night=180000.00,
                bedrooms=3,
                bathrooms=3,
                category_id=cat_3bed.category_id,
                is_featured=True,
                status='available'
            )
            apt2 = Apartment(
                title='2-Bedrooms well funished (Unit 1)',
                description='Expansive living room, executive work station & chef-inspired kitchen tailored for corporate executives.',
                price_per_night=135000.00,
                bedrooms=2,
                bathrooms=2,
                category_id=cat_2bed.category_id,
                is_featured=True,
                status='available'
            )
            apt2_unit2 = Apartment(
                title='2-Bedrooms Diplomatic Suite (Unit 2)',
                description='Expansive living room, executive work station & chef-inspired kitchen tailored for corporate executives.',
                price_per_night=135000.00,
                bedrooms=2,
                bathrooms=2,
                category_id=cat_2bed.category_id,
                is_featured=True,
                status='available'
            )
            apt3 = Apartment(
                title='1-Bedroom tastefully finished',
                description='Ideal for short stays with plush lounge area and swimming pool access.',
                price_per_night=65000.00,
                bedrooms=1,
                bathrooms=1,
                category_id=cat_1bed.category_id,
                is_featured=True,
                status='available'
            )
            apt4 = Apartment(
                title='Studio Apartment Premium',
                description='Cozy modern layout for solo business traveler or couple seeking high-end luxury.',
                price_per_night=45000.00,
                bedrooms=1,
                bathrooms=1,
                category_id=cat_studio.category_id,
                is_featured=True,
                status='available'
            )
            db.session.add_all([apt1, apt1_unit2, apt2, apt2_unit2, apt3, apt4])
            db.session.commit()
            print("[OK] Apartment inventory seeded (2x 3-Bedrooms, 2x 2-Bedrooms).")
    finally:
        if ctx:
            ctx.pop()

if __name__ == '__main__':
    seed_database()
    print("[OK] Starting local Flask server on http://127.0.0.1:5050")
    app.run(host='127.0.0.1', port=5050, debug=True)