from datetime import datetime, timezone
from pkg.extensions import db

class Payment(db.Model):
    __tablename__ = 'payments'

    payment_id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.booking_id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    verified_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    refunded_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)

    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(30), default='bank_transfer', nullable=False)  # bank_transfer, card, cash, paystack
    transaction_ref = db.Column(db.String(100), unique=True, nullable=True)
    payment_proof = db.Column(db.String(255), nullable=True)
    gateway_response = db.Column(db.Text, nullable=True)  # JSON string
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, verified, rejected, refunded

    verified_at = db.Column(db.DateTime, nullable=True)
    refunded_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Payment id={self.payment_id} amount=₦{self.amount} status={self.status}>"
