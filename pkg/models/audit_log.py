from datetime import datetime, timezone
from pkg.extensions import db

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    log_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    activity_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    module = db.Column(db.String(50), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    old_values = db.Column(db.Text, nullable=True)  # JSON string
    new_values = db.Column(db.Text, nullable=True)  # JSON string
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<AuditLog {self.module}:{self.action} by user_id={self.user_id}>"


class AdminActionLog(db.Model):
    __tablename__ = 'admin_action_logs'

    log_id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    target_user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    action_type = db.Column(db.String(50), nullable=False)
    previous_status = db.Column(db.String(50), nullable=True)
    new_status = db.Column(db.String(50), nullable=True)
    reason = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class SuperAdminActionLog(db.Model):
    __tablename__ = 'superadmin_action_logs'

    log_id = db.Column(db.Integer, primary_key=True)
    superadmin_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    target_admin_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    target_agent_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    action_type = db.Column(db.String(50), nullable=False)  # override_role, deactivate, delete
    previous_role = db.Column(db.String(50), nullable=True)
    new_role = db.Column(db.String(50), nullable=True)
    reason = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class SystemSettings(db.Model):
    __tablename__ = 'system_settings'

    setting_id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text, nullable=True)
    setting_group = db.Column(db.String(50), default='general', nullable=False)
    is_public = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
