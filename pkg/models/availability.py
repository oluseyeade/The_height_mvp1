from datetime import datetime, timezone
from pkg.extensions import db

class Availability(db.Model):
    __tablename__ = 'availabilities'

    availability_id = db.Column(db.Integer, primary_key=True)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartments.apartment_id'), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.String(20), default='available', nullable=False)  # available, booked, blocked
    price_override = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    apartment_info = db.relationship('Apartment', backref='availability_dates')

    def __repr__(self):
        return f"<Availability apt_id={self.apartment_id} date={self.date} status={self.status}>"
