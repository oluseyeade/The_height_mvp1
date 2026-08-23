from datetime import datetime, timezone
from pkg.extensions import db

class Notification(db.Model):
    __tablename__ = 'notifications'

    notification_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.booking_id'), nullable=True)
    
    type = db.Column(db.String(50), nullable=False)  # booking, payment, review, reminder, promotional
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(255), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime, nullable=True)
    priority = db.Column(db.String(20), default='medium')  # high, medium, low
    channel = db.Column(db.String(30), default='in-app')  # email, whatsapp, sms, in-app

    sent_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class EmailLog(db.Model):
    __tablename__ = 'email_logs'

    email_id = db.Column(db.Integer, primary_key=True)
    recipient = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    template_name = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default='sent', nullable=False)  # pending, sent, failed
    error_message = db.Column(db.Text, nullable=True)
    retry_count = db.Column(db.Integer, default=0)
    sent_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class WhatsAppLog(db.Model):
    __tablename__ = 'whatsapp_logs'

    whatsapp_id = db.Column(db.Integer, primary_key=True)
    recipient = db.Column(db.String(30), nullable=False)
    message = db.Column(db.Text, nullable=False)
    template_name = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default='sent', nullable=False)  # pending, sent, delivered, read, failed
    delivered_at = db.Column(db.DateTime, nullable=True)
    read_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    sent_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
