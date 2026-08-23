from pkg.extensions import db
from pkg.models.user import Role, User, Admin, RoleHierarchy

def seed_roles_and_superadmin():
    db.create_all()

    roles_data = [
        {'name': 'User', 'description': 'Standard registered customer', 'level': RoleHierarchy.USER, 'can_override': False},
        {'name': 'Agent', 'description': 'Registered agent with commission tracking', 'level': RoleHierarchy.AGENT, 'can_override': False},
        {'name': 'Admin', 'description': 'Apartment & Booking Administrator', 'level': RoleHierarchy.ADMIN, 'can_override': False},
        {'name': 'SuperAdmin', 'description': 'System Super Administrator with override capabilities', 'level': RoleHierarchy.SUPERADMIN, 'can_override': True},
    ]

    for rdata in roles_data:
        existing_role = Role.query.filter_by(role_name=rdata['name']).first()
        if not existing_role:
            role = Role(
                role_name=rdata['name'],
                description=rdata['description'],
                hierarchy_level=rdata['level'],
                can_override=rdata['can_override']
            )
            db.session.add(role)
    
    db.session.commit()
    print("Roles seeded.")

    # Create default SuperAdmin if not existing
    superadmin_role = Role.query.filter_by(role_name='SuperAdmin').first()
    superadmin_email = 'superadmin@theheightapartment.com'

    existing_superadmin = User.query.filter_by(email=superadmin_email).first()
    if not existing_superadmin:
        admin_user = User(
            full_name='Super Administrator',
            email=superadmin_email,
            phone='+2348000000000',
            role_id=superadmin_role.role_id,
            status='active'
        )
        admin_user.set_password('SuperAdmin@2026')
        db.session.add(admin_user)
        db.session.commit()

        admin_profile = Admin(
            user_id=admin_user.user_id,
            can_manage_agents=True,
            can_manage_apartments=True,
            can_manage_bookings=True,
            can_manage_payments=True,
            can_manage_reviews=True,
            can_manage_corporate=True,
            can_upload_images=True
        )
        db.session.add(admin_profile)
        db.session.commit()
        print(f"Default SuperAdmin created: {superadmin_email} / SuperAdmin@2026")
    else:
        print("SuperAdmin already exists.")
