import uuid
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db, login_manager

# -----------------------------------------------------------------------------
# User & Role Models
# -----------------------------------------------------------------------------
class Role(db.Model):
    __tablename__ = 'roles'

    role_id = db.Column(db.Integer, primary_key=True)
    role_name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    hierarchy_level = db.Column(db.Integer, nullable=False, default=1)
    can_override = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    users = db.relationship('User', backref='role', lazy=True)

    def __repr__(self):
        return f"<Role {self.role_name}>"

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    user_id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.role_id'), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    status = db.Column(db.String(20), default='active')
    profile_image = db.Column(db.String(255), nullable=True)
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    profile = db.relationship('UserProfile', backref='user', uselist=False, cascade='all, delete-orphan')
    admin_profile = db.relationship('Admin', backref='user', uselist=False, foreign_keys='Admin.user_id')
    superadmin_profile = db.relationship('SuperAdmin', backref='user', uselist=False, foreign_keys='SuperAdmin.user_id')
    agent_profile = db.relationship('Agent', backref='user', uselist=False, foreign_keys='Agent.user_id')
    bookings = db.relationship('Booking', backref='user', lazy=True)
    reviews = db.relationship('Review', backref='user', foreign_keys='Review.user_id', lazy=True)

    def get_id(self):
        return str(self.user_id)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_superadmin(self):
        return self.role and self.role.hierarchy_level == 4

    @property
    def is_admin(self):
        return self.role and self.role.hierarchy_level >= 3

    @property
    def is_agent(self):
        return self.role and self.role.role_name == 'Agent'

    def __repr__(self):
        return f"<User {self.email}>"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class UserProfile(db.Model):
    __tablename__ = 'user_profiles'

    profile_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, unique=True)
    address = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(100), nullable=True)
    newsletter_sub = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Admin(db.Model):
    __tablename__ = 'admins'

    admin_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, unique=True)
    can_manage_agents = db.Column(db.Boolean, default=True)
    can_manage_apartments = db.Column(db.Boolean, default=True)
    can_manage_bookings = db.Column(db.Boolean, default=True)
    can_manage_payments = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)
    deactivated_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    deactivated_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SuperAdmin(db.Model):
    __tablename__ = 'super_admins'

    superadmin_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, unique=True)
    can_override_roles = db.Column(db.Boolean, default=True)
    can_delete_admins = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# -----------------------------------------------------------------------------
# Agent & Commission Models
# -----------------------------------------------------------------------------
class Agent(db.Model):
    __tablename__ = 'agents'

    agent_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, unique=True)
    agent_code = db.Column(db.String(20), unique=True, nullable=False, default=lambda: f"AGT-THA-{uuid.uuid4().hex[:6].upper()}")
    commission_rate = db.Column(db.Numeric(5, 2), default=10.00)
    total_earnings = db.Column(db.Numeric(10, 2), default=0.00)
    pending_commission = db.Column(db.Numeric(10, 2), default=0.00)
    bank_name = db.Column(db.String(100), nullable=True)
    account_number = db.Column(db.String(30), nullable=True)
    account_holder_name = db.Column(db.String(150), nullable=True)
    status = db.Column(db.String(20), default='pending')
    document_upload_path = db.Column(db.String(255), nullable=True)
    deactivated_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    deleted_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)

    commissions = db.relationship('AgentCommission', backref='agent', lazy=True)
    bookings = db.relationship('Booking', backref='agent', lazy=True)

    @classmethod
    def find_by_code(cls, agent_code):
        if not agent_code:
            return None
        agent_code = str(agent_code).strip()
        if not agent_code:
            return None
        return cls.query.filter_by(agent_code=agent_code.upper()).first()

class AgentCommission(db.Model):
    __tablename__ = 'agent_commissions'

    commission_id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.agent_id'), nullable=False)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.booking_id'), nullable=False)
    booking_amount = db.Column(db.Numeric(10, 2), nullable=False)
    commission_percentage = db.Column(db.Numeric(5, 2), nullable=False)
    commission_amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_status = db.Column(db.String(20), default='pending')
    paid_date = db.Column(db.DateTime, nullable=True)
    payment_reference = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    # Extended Enterprise Agent Tracking
    payment_verified = db.Column(db.Boolean, default=False)
    commission_rate = db.Column(db.Numeric(5, 2), default=7.00)
    payout_status = db.Column(db.String(30), default='pending')
    payout_date = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Commission(db.Model):
    __tablename__ = 'commissions'

    commission_id = db.Column(db.Integer, primary_key=True)
    commission_reference = db.Column(db.String(50), unique=True, nullable=False, index=True, default=lambda: f"COM-THA-{uuid.uuid4().hex[:8].upper()}")
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.booking_id'), unique=True, nullable=False, index=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.agent_id'), nullable=False, index=True)
    referral_code = db.Column(db.String(50), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    property_id = db.Column(db.Integer, db.ForeignKey('properties.property_id'), nullable=True)
    payment_reference = db.Column(db.String(100), unique=True, nullable=False, index=True)
    payment_provider = db.Column(db.String(30), default='PAYSTACK')
    
    booking_amount = db.Column(db.Numeric(10, 2), nullable=False)
    discount_percentage = db.Column(db.Numeric(5, 2), default=3.00)
    discount_amount = db.Column(db.Numeric(10, 2), default=0.00)
    net_booking_amount = db.Column(db.Numeric(10, 2), nullable=False)
    commission_percentage = db.Column(db.Numeric(5, 2), default=7.00)
    commission_amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(10), default='NGN')
    
    commission_status = db.Column(db.String(30), default='PENDING', index=True)
    payment_status = db.Column(db.String(30), default='PENDING')
    commission_type = db.Column(db.String(30), default='REFERRAL')
    
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    approved_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    metadata_json = db.Column(db.Text, nullable=True)

    agent = db.relationship('Agent', backref='enterprise_commissions', lazy=True)
    booking = db.relationship('Booking', foreign_keys=[booking_id], lazy=True)
    customer = db.relationship('User', foreign_keys=[customer_id], lazy=True)
    property = db.relationship('Property', foreign_keys=[property_id], lazy=True)
    approver = db.relationship('User', foreign_keys=[approved_by], lazy=True)
    audit_logs = db.relationship('CommissionAuditLog', backref='commission', lazy=True, cascade='all, delete-orphan')

class CommissionAuditLog(db.Model):
    __tablename__ = 'commission_audit_logs'

    log_id = db.Column(db.Integer, primary_key=True)
    commission_id = db.Column(db.Integer, db.ForeignKey('commissions.commission_id'), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False)
    old_status = db.Column(db.String(30), nullable=True)
    new_status = db.Column(db.String(30), nullable=True)
    performed_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    performed_at = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45), nullable=True)
    device = db.Column(db.String(255), nullable=True)
    remarks = db.Column(db.Text, nullable=True)

class ReferralHistory(db.Model):
    __tablename__ = 'referral_history'

    referral_history_id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.booking_id'), nullable=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.agent_id'), nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    referral_code = db.Column(db.String(50), nullable=False, index=True)
    session_id = db.Column(db.String(100), nullable=True)
    browser_fingerprint = db.Column(db.String(255), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    landing_page = db.Column(db.String(255), nullable=True)
    referral_source = db.Column(db.String(100), nullable=True)
    qr_used = db.Column(db.Boolean, default=False)
    link_used = db.Column(db.Boolean, default=True)
    validated = db.Column(db.Boolean, default=False)
    validation_message = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

# -----------------------------------------------------------------------------
# Property & Apartment Models
# -----------------------------------------------------------------------------
class Property(db.Model):
    __tablename__ = 'properties'

    property_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100), default='Lagos')
    state = db.Column(db.String(100), default='Lagos State')
    phone = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    description = db.Column(db.Text, nullable=True)
    logo_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    apartments = db.relationship('Apartment', backref='property', lazy=True)

class PropertySettings(db.Model):
    __tablename__ = 'property_settings'

    settings_id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('properties.property_id'), nullable=False)
    company_name = db.Column(db.String(150), default='The Height Apartment')
    company_phone = db.Column(db.String(50), default='+234 800 000 0000')
    company_email = db.Column(db.String(120), default='info@theheightapartment.com')
    caution_fee_amount = db.Column(db.Numeric(10, 2), default=50000.00)
    booking_deposit_amount = db.Column(db.Numeric(10, 2), default=50000.00)
    bank_name = db.Column(db.String(100), nullable=True)
    account_number = db.Column(db.String(30), nullable=True)
    account_name = db.Column(db.String(150), nullable=True)

class Category(db.Model):
    __tablename__ = 'categories'

    category_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    icon = db.Column(db.String(50), default='fa-building')
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

    apartments = db.relationship('Apartment', backref='category', lazy=True)

class Apartment(db.Model):
    __tablename__ = 'apartments'

    apartment_id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('properties.property_id'), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.category_id'), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price_per_night = db.Column(db.Numeric(10, 2), nullable=False)
    bedrooms = db.Column(db.Integer, default=1)
    bathrooms = db.Column(db.Integer, default=1)
    capacity = db.Column(db.Integer, default=2)
    square_feet = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), default='available')
    is_featured = db.Column(db.Boolean, default=False)
    view_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    images = db.relationship('ApartmentImage', backref='apartment', lazy=True, cascade='all, delete-orphan')
    amenities = db.relationship('ApartmentAmenity', backref='apartment', lazy=True, cascade='all, delete-orphan')
    facilities = db.relationship('ApartmentFacility', backref='apartment', lazy=True, cascade='all, delete-orphan')
    bookings = db.relationship('Booking', backref='apartment', lazy=True)
    availabilities = db.relationship('Availability', backref='apartment', lazy=True, cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='apartment', lazy=True)

    @property
    def cover_image(self):
        cover = next((img for img in self.images if img.is_cover), None)
        if cover:
            return cover.image_url
        elif self.images:
            return self.images[0].image_url
        return 'images/apartments/default.jpg'

    @property
    def display_title(self):
        title = str(self.title or '')
        for suffix in ['(Unit 1)', '(Unit 2)', 'Unit 1', 'Unit 2', '(Unit 01)', '(Unit 02)', '3BR-01', '3BR-02', '2BR-01', '2BR-02']:
            title = title.replace(suffix, '')
        return title.strip()

class ApartmentImage(db.Model):
    __tablename__ = 'apartment_images'

    image_id = db.Column(db.Integer, primary_key=True)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartments.apartment_id'), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    image_url = db.Column(db.String(255), nullable=False)
    is_cover = db.Column(db.Boolean, default=False)
    caption = db.Column(db.String(150), nullable=True)
    sort_order = db.Column(db.Integer, default=0)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)

class Amenity(db.Model):
    __tablename__ = 'amenities'

    amenity_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(50), default='fa-check-circle')
    category = db.Column(db.String(50), default='general')
    is_active = db.Column(db.Boolean, default=True)

class Facility(db.Model):
    __tablename__ = 'facilities'

    facility_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(50), default='fa-concierge-bell')
    description = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True)

class ApartmentAmenity(db.Model):
    __tablename__ = 'apartment_amenities'

    id = db.Column(db.Integer, primary_key=True)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartments.apartment_id'), nullable=False)
    amenity_id = db.Column(db.Integer, db.ForeignKey('amenities.amenity_id'), nullable=False)

    amenity = db.relationship('Amenity')

class ApartmentFacility(db.Model):
    __tablename__ = 'apartment_facilities'

    id = db.Column(db.Integer, primary_key=True)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartments.apartment_id'), nullable=False)
    facility_id = db.Column(db.Integer, db.ForeignKey('facilities.facility_id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)

    facility = db.relationship('Facility')

# -----------------------------------------------------------------------------
# Booking & Payment Models
# -----------------------------------------------------------------------------
class Booking(db.Model):
    __tablename__ = 'bookings'

    booking_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartments.apartment_id'), nullable=False)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.agent_id'), nullable=True)
    check_in = db.Column(db.Date, nullable=False)
    check_out = db.Column(db.Date, nullable=False)
    guest_count = db.Column(db.Integer, default=1)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    discount_amount = db.Column(db.Numeric(10, 2), default=0.00)
    final_amount = db.Column(db.Numeric(10, 2), nullable=False)
    caution_fee_amount = db.Column(db.Numeric(10, 2), default=50000.00)
    caution_fee_status = db.Column(db.String(30), default='Pending Transfer')
    booking_ref = db.Column(db.String(30), unique=True, nullable=False, default=lambda: f"THA-{uuid.uuid4().hex[:8].upper()}")
    status = db.Column(db.String(20), default='pending')
    
    # Extended Enterprise Fields
    apartment_fee = db.Column(db.Numeric(10, 2), nullable=True)
    discount_percentage = db.Column(db.Numeric(5, 2), default=0.00)
    caution_fee = db.Column(db.Numeric(10, 2), default=50000.00)
    total_amount = db.Column(db.Numeric(10, 2), nullable=True)
    payment_status = db.Column(db.String(30), default='PENDING_PAYMENT')
    booking_status = db.Column(db.String(30), default='Pending Payment')
    refund_status = db.Column(db.String(30), default='NOT_APPLICABLE')
    payment_reference = db.Column(db.String(100), nullable=True)
    commission_generated = db.Column(db.Boolean, default=False)
    commission_id = db.Column(db.Integer, db.ForeignKey('commissions.commission_id'), nullable=True)
    checked_in_at = db.Column(db.DateTime, nullable=True)
    checked_out_at = db.Column(db.DateTime, nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    inspection_status = db.Column(db.String(30), default='NOT_INSPECTED')

    guest_name = db.Column(db.String(120), nullable=True)
    guest_email = db.Column(db.String(120), nullable=True)
    guest_phone = db.Column(db.String(30), nullable=True)
    special_requests = db.Column(db.Text, nullable=True)
    source = db.Column(db.String(30), default='website')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    payments = db.relationship('Payment', backref='booking', lazy=True)
    reviews = db.relationship('Review', backref='booking', lazy=True)
    inspections = db.relationship('Inspection', backref='booking', lazy=True)
    refunds = db.relationship('Refund', backref='booking', lazy=True)

class Availability(db.Model):
    __tablename__ = 'availabilities'

    availability_id = db.Column(db.Integer, primary_key=True)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartments.apartment_id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='booked')
    price_override = db.Column(db.Numeric(10, 2), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Payment(db.Model):
    __tablename__ = 'payments'

    payment_id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.booking_id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    verified_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    transaction_ref = db.Column(db.String(100), nullable=True)
    payment_proof_path = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default='pending')
    verified_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # Extended Enterprise Payment Fields
    paystack_reference = db.Column(db.String(100), nullable=True)
    callback_payload = db.Column(db.Text, nullable=True)
    payment_channel = db.Column(db.String(50), default='bank_transfer')
    payment_gateway = db.Column(db.String(50), default='paystack')
    payment_source = db.Column(db.String(50), default='website')
    verification_status = db.Column(db.String(30), default='pending')
    receipt_number = db.Column(db.String(50), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id], lazy=True)
    verifier = db.relationship('User', foreign_keys=[verified_by], lazy=True)
    receipt = db.relationship('Receipt', backref='payment', uselist=False)

# -----------------------------------------------------------------------------
# Property Damage Inspection & Caution Fee Refund Models
# -----------------------------------------------------------------------------
class Inspection(db.Model):
    __tablename__ = 'inspections'

    inspection_id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.booking_id'), nullable=False)
    inspector_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    inspection_date = db.Column(db.DateTime, default=datetime.utcnow)
    property_condition = db.Column(db.String(50), default='excellent')
    furniture_status = db.Column(db.String(50), default='good')
    electronics_status = db.Column(db.String(50), default='good')
    kitchen_status = db.Column(db.String(50), default='good')
    bathroom_status = db.Column(db.String(50), default='good')
    keys_status = db.Column(db.String(50), default='returned')
    remotes_status = db.Column(db.String(50), default='returned')
    damage_found = db.Column(db.Boolean, default=False)
    damage_description = db.Column(db.Text, nullable=True)
    estimated_repair_cost = db.Column(db.Numeric(10, 2), default=0.00)
    photos_json = db.Column(db.Text, nullable=True)
    recommendation = db.Column(db.String(50), default='full_refund')
    approval_status = db.Column(db.String(30), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    inspector = db.relationship('User', foreign_keys=[inspector_id], lazy=True)

class Refund(db.Model):
    __tablename__ = 'refunds'

    refund_id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.booking_id'), nullable=False)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.payment_id'), nullable=True)
    inspection_id = db.Column(db.Integer, db.ForeignKey('inspections.inspection_id'), nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    refund_amount = db.Column(db.Numeric(10, 2), nullable=False)
    refund_reason = db.Column(db.Text, nullable=False)
    refund_type = db.Column(db.String(30), default='full')
    refund_status = db.Column(db.String(30), default='pending_approval')
    approved_at = db.Column(db.DateTime, nullable=True)
    processed_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    approver = db.relationship('User', foreign_keys=[approved_by], lazy=True)

class Receipt(db.Model):
    __tablename__ = 'receipts'

    receipt_id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.payment_id'), nullable=False, unique=True)
    receipt_number = db.Column(db.String(50), unique=True, nullable=False, default=lambda: f"RCP-THA-{uuid.uuid4().hex[:6].upper()}")
    pdf_path = db.Column(db.String(255), nullable=True)
    qr_code_path = db.Column(db.String(255), nullable=True)
    booking_details_json = db.Column(db.Text, nullable=True)
    email_sent = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime, nullable=True)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)

# -----------------------------------------------------------------------------
# Corporate & Contact Models
# -----------------------------------------------------------------------------
class CorporateEnquiry(db.Model):
    __tablename__ = 'corporate_enquiries'

    enquiry_id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(150), nullable=False)
    contact_person = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    check_in = db.Column(db.Date, nullable=False)
    check_out = db.Column(db.Date, nullable=False)
    guest_count = db.Column(db.Integer, default=1)
    suite_count = db.Column(db.Integer, default=1)
    length_of_stay = db.Column(db.Integer, nullable=True)
    budget_range = db.Column(db.String(50), nullable=True)
    special_requests = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), default='new')
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartments.apartment_id'), nullable=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.booking_id'), nullable=True)
    payment_status = db.Column(db.String(30), default='PENDING')
    payment_reference = db.Column(db.String(100), nullable=True)
    quoted_amount = db.Column(db.Numeric(10, 2), default=0.00)
    caution_fee = db.Column(db.Numeric(10, 2), default=50000.00)
    total_amount = db.Column(db.Numeric(10, 2), default=0.00)
    internal_notes = db.Column(db.Text, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    rejected_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    assigned_admin = db.relationship('User', foreign_keys=[assigned_to], lazy=True)
    approver = db.relationship('User', foreign_keys=[approved_by], lazy=True)
    rejecter = db.relationship('User', foreign_keys=[rejected_by], lazy=True)
    apartment = db.relationship('Apartment', foreign_keys=[apartment_id], lazy=True)
    booking = db.relationship('Booking', foreign_keys=[booking_id], lazy=True)
    quotes = db.relationship('CorporateQuote', backref='enquiry', lazy=True, cascade='all, delete-orphan')
    audit_logs = db.relationship('CorporateAuditLog', backref='enquiry', lazy=True, cascade='all, delete-orphan')

class CorporateAuditLog(db.Model):
    __tablename__ = 'corporate_audit_logs'

    log_id = db.Column(db.Integer, primary_key=True)
    enquiry_id = db.Column(db.Integer, db.ForeignKey('corporate_enquiries.enquiry_id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    old_status = db.Column(db.String(30), nullable=True)
    new_status = db.Column(db.String(30), nullable=True)
    performed_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    performer = db.relationship('User', foreign_keys=[performed_by], lazy=True)

class CorporateQuote(db.Model):
    __tablename__ = 'corporate_quotes'

    quote_id = db.Column(db.Integer, primary_key=True)
    enquiry_id = db.Column(db.Integer, db.ForeignKey('corporate_enquiries.enquiry_id'), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    quote_number = db.Column(db.String(40), unique=True, nullable=False, default=lambda: f"QT-THA-{uuid.uuid4().hex[:6].upper()}")
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    discount = db.Column(db.Numeric(10, 2), default=0.00)
    final_amount = db.Column(db.Numeric(10, 2), nullable=False)
    room_type = db.Column(db.String(100), nullable=False)
    inclusions = db.Column(db.Text, nullable=True)
    terms = db.Column(db.Text, nullable=True)
    valid_until = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(30), default='draft')
    sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ContactMessage(db.Model):
    __tablename__ = 'contact_messages'

    message_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    subject = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='new')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# -----------------------------------------------------------------------------
# Review & Audit Models
# -----------------------------------------------------------------------------
class Review(db.Model):
    __tablename__ = 'reviews'

    review_id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.booking_id'), nullable=False, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartments.apartment_id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(150), nullable=True)
    comment = db.Column(db.Text, nullable=False)
    is_verified = db.Column(db.Boolean, default=True)
    is_public = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='approved')
    approved_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    approver = db.relationship('User', foreign_keys=[approved_by], lazy=True)
    response = db.relationship('ReviewResponse', backref='review', uselist=False, cascade='all, delete-orphan')

class ReviewResponse(db.Model):
    __tablename__ = 'review_responses'

    response_id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('reviews.review_id'), nullable=False, unique=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    response = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    log_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    activity_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    module = db.Column(db.String(50), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AdminActionLog(db.Model):
    __tablename__ = 'admin_action_logs'

    log_id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    target_user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    action_type = db.Column(db.String(100), nullable=False)
    previous_status = db.Column(db.String(50), nullable=True)
    new_status = db.Column(db.String(50), nullable=True)
    reason = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SuperAdminActionLog(db.Model):
    __tablename__ = 'superadmin_action_logs'

    log_id = db.Column(db.Integer, primary_key=True)
    superadmin_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    target_admin_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    target_agent_id = db.Column(db.Integer, db.ForeignKey('agents.agent_id'), nullable=True)
    action_type = db.Column(db.String(100), nullable=False)
    previous_role = db.Column(db.String(50), nullable=True)
    new_role = db.Column(db.String(50), nullable=True)
    reason = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class EmailLog(db.Model):
    __tablename__ = 'email_logs'

    email_id = db.Column(db.Integer, primary_key=True)
    recipient = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='sent')
    error_message = db.Column(db.Text, nullable=True)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)

class WhatsAppLog(db.Model):
    __tablename__ = 'whatsapp_logs'

    whatsapp_id = db.Column(db.Integer, primary_key=True)
    recipient = db.Column(db.String(30), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='sent')
    delivered_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)

class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True, index=True)
    notification_type = db.Column(db.String(100), nullable=False, index=True)
    portal = db.Column(db.String(50), nullable=False, index=True) # ADMIN, AGENTS, INSPECTIONS, BOOKINGS, CORPORATE, REVIEWS, AUDIT
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), default='MEDIUM', nullable=False) # LOW, MEDIUM, HIGH, CRITICAL
    status = db.Column(db.String(20), default='UNREAD', nullable=False) # UNREAD, READ, ACTION_REQUIRED, RESOLVED
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    requires_action = db.Column(db.Boolean, default=False, nullable=False, index=True)
    related_id = db.Column(db.Integer, nullable=True)
    related_type = db.Column(db.String(50), nullable=True)
    action_url = db.Column(db.String(255), nullable=True)
    dedup_key = db.Column(db.String(100), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    read_at = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)

    recipient = db.relationship('User', foreign_keys=[recipient_id], lazy=True)


class SuperadminOTP(db.Model):
    __tablename__ = 'superadmin_otps'

    otp_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, index=True)
    otp_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    attempts = db.Column(db.Integer, default=0, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', foreign_keys=[user_id], lazy=True)


