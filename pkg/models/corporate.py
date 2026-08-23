import secrets
from datetime import datetime, timezone
from pkg.extensions import db

class CorporateEnquiry(db.Model):
    __tablename__ = 'corporate_enquiries'

    enquiry_id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(120), nullable=False)
    contact_person = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=False)
    
    check_in = db.Column(db.Date, nullable=False)
    check_out = db.Column(db.Date, nullable=False)
    guest_count = db.Column(db.Integer, default=1, nullable=False)
    suite_count = db.Column(db.Integer, default=1, nullable=False)
    length_of_stay = db.Column(db.Integer, nullable=False)  # in days
    budget_range = db.Column(db.String(50), nullable=True)
    special_requests = db.Column(db.Text, nullable=True)
    
    status = db.Column(db.String(30), default='new', nullable=False)  # new, reviewed, quoted, confirmed, lost
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    quotes = db.relationship('CorporateQuote', backref='enquiry', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<CorporateEnquiry company='{self.company_name}' ({self.status})>"


class CorporateQuote(db.Model):
    __tablename__ = 'corporate_quotes'

    quote_id = db.Column(db.Integer, primary_key=True)
    enquiry_id = db.Column(db.Integer, db.ForeignKey('corporate_enquiries.enquiry_id'), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    
    quote_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, default=0.0)
    final_amount = db.Column(db.Float, nullable=False)
    room_type = db.Column(db.String(100), nullable=False)
    inclusions_json = db.Column(db.Text, nullable=True)  # JSON list
    terms = db.Column(db.Text, nullable=True)
    valid_until = db.Column(db.Date, nullable=False)
    
    status = db.Column(db.String(30), default='sent', nullable=False)  # draft, sent, accepted, rejected, expired
    sent_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    accepted_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    @staticmethod
    def generate_number():
        return f"THA-CQT-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"

    def __repr__(self):
        return f"<CorporateQuote {self.quote_number} final=₦{self.final_amount:,.2f}>"
