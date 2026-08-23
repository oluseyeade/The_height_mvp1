import secrets
from datetime import datetime, timezone
from pkg.extensions import db

class Booking(db.Model):
    __tablename__ = 'bookings'

    booking_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)  # Nullable for optional guest booking
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartments.apartment_id'), nullable=False)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.agent_id'), nullable=True)

    booking_ref = db.Column(db.String(30), unique=True, nullable=False, index=True)
    check_in = db.Column(db.Date, nullable=False)
    check_out = db.Column(db.Date, nullable=False)
    guest_count = db.Column(db.Integer, default=1, nullable=False)

    # Guest details if not registered
    guest_name = db.Column(db.String(120), nullable=True)
    guest_email = db.Column(db.String(120), nullable=True)
    guest_phone = db.Column(db.String(30), nullable=True)

    # Pricing & Deposit
    price_per_night = db.Column(db.Float, nullable=False)
    total_nights = db.Column(db.Integer, nullable=False, default=1)
    total_price = db.Column(db.Float, nullable=False)
    discount_amount = db.Column(db.Float, default=0.0)
    final_amount = db.Column(db.Float, nullable=False)
    deposit_required = db.Column(db.Float, default=50000.0, nullable=False)  # ₦50,000 fixed deposit policy

    status = db.Column(db.String(30), default='pending', nullable=False)  # pending, confirmed, checked-in, checked-out, cancelled, no-show
    source = db.Column(db.String(30), default='website', nullable=False)  # website, agent, corporate, walk-in
    special_requests = db.Column(db.Text, nullable=True)
    cancellation_reason = db.Column(db.Text, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    apartment = db.relationship('Apartment', backref='bookings')
    user = db.relationship('User', backref='bookings')
    payments = db.relationship('Payment', backref='booking', lazy=True, cascade='all, delete-orphan')

    @staticmethod
    def generate_reference():
        return f"THA-BK-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"

    def __repr__(self):
        return f"<Booking {self.booking_ref} apt_id={self.apartment_id} ({self.status})>"
