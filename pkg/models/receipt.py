import secrets
from datetime import datetime, timezone
from pkg.extensions import db

class Receipt(db.Model):
    __tablename__ = 'receipts'

    receipt_id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.payment_id'), unique=True, nullable=False)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.booking_id'), nullable=False)
    
    receipt_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    pdf_path = db.Column(db.String(255), nullable=True)
    qr_code_path = db.Column(db.String(255), nullable=True)
    booking_details_json = db.Column(db.Text, nullable=True)  # Snapshot JSON string
    email_sent = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime, nullable=True)

    generated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    payment = db.relationship('Payment', backref=db.backref('receipt', uselist=False))
    booking = db.relationship('Booking', backref=db.backref('receipt', uselist=False))

    @staticmethod
    def generate_number():
        return f"THA-RCT-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"

    def __repr__(self):
        return f"<Receipt {self.receipt_number} payment_id={self.payment_id}>"
