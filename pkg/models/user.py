from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from pkg.extensions import db

class RoleHierarchy:
    USER = 1
    AGENT = 2
    ADMIN = 3
    SUPERADMIN = 4

class Role(db.Model):
    __tablename__ = 'roles'

    role_id = db.Column(db.Integer, primary_key=True)
    role_name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    hierarchy_level = db.Column(db.Integer, nullable=False, default=RoleHierarchy.USER)
    can_override = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    users = db.relationship('User', backref='role', lazy=True)

    def __repr__(self):
        return f"<Role {self.role_name} (Level {self.hierarchy_level})>"


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    user_id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.role_id'), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='active', nullable=False)  # active, inactive, suspended, deleted
    profile_image = db.Column(db.String(255), nullable=True, default='default_avatar.png')
    last_login = db.Column(db.DateTime, nullable=True)
    email_verified_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships with explicit foreign_keys to resolve ambiguity
    admin_profile = db.relationship('Admin', foreign_keys='Admin.user_id', backref='user', uselist=False, cascade='all, delete-orphan')
    agent_profile = db.relationship('Agent', foreign_keys='Agent.user_id', backref='user', uselist=False, cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', foreign_keys='AuditLog.user_id', backref='user', lazy=True)

    def get_id(self):
        return str(self.user_id)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_superadmin(self):
        return self.role and self.role.hierarchy_level == RoleHierarchy.SUPERADMIN

    @property
    def is_admin(self):
        return self.role and self.role.hierarchy_level >= RoleHierarchy.ADMIN

    @property
    def is_agent(self):
        return self.role and self.role.hierarchy_level == RoleHierarchy.AGENT

    def __repr__(self):
        return f"<User {self.email} ({self.role.role_name if self.role else 'No Role'})>"


class Admin(db.Model):
    __tablename__ = 'admins'

    admin_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), unique=True, nullable=False)
    permissions = db.Column(db.Text, nullable=True)  # JSON formatted permission list/dict
    can_manage_agents = db.Column(db.Boolean, default=True)
    can_manage_apartments = db.Column(db.Boolean, default=True)
    can_manage_bookings = db.Column(db.Boolean, default=True)
    can_manage_payments = db.Column(db.Boolean, default=True)
    can_manage_reviews = db.Column(db.Boolean, default=True)
    can_manage_corporate = db.Column(db.Boolean, default=True)
    can_upload_images = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)
    deactivated_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    deactivated_at = db.Column(db.DateTime, nullable=True)
    deleted_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Admin user_id={self.user_id}>"


class Agent(db.Model):
    __tablename__ = 'agents'

    agent_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), unique=True, nullable=False)
    agent_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    commission_rate = db.Column(db.Float, default=5.0, nullable=False)  # Percentage
    total_earnings = db.Column(db.Float, default=0.0)
    pending_commission = db.Column(db.Float, default=0.0)
    bank_name = db.Column(db.String(100), nullable=True)
    account_number = db.Column(db.String(30), nullable=True)
    account_holder_name = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, active, suspended, deleted
    document_upload_path = db.Column(db.String(255), nullable=True)
    verification_doc = db.Column(db.String(255), nullable=True)
    deactivated_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    deactivated_at = db.Column(db.DateTime, nullable=True)
    deleted_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    registration_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Agent code={self.agent_code} user_id={self.user_id}>"
