from datetime import datetime, timezone
from pkg.extensions import db

class Review(db.Model):
    __tablename__ = 'reviews'

    review_id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.booking_id'), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    apartment_id = db.Column(db.Integer, db.ForeignKey('apartments.apartment_id'), nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)

    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    title = db.Column(db.String(150), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    images_json = db.Column(db.Text, nullable=True)  # JSON array
    is_verified = db.Column(db.Boolean, default=True, nullable=False)  # "Verified Guest" badge
    is_public = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='approved', nullable=False)  # pending, approved, rejected

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    booking = db.relationship('Booking', backref=db.backref('review', uselist=False))
    apartment = db.relationship('Apartment', backref='reviews')
    user = db.relationship('User', foreign_keys=[user_id], backref='reviews')
    responses = db.relationship('ReviewResponse', backref='review', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Review rating={self.rating}/5 booking_id={self.booking_id}>"


class ReviewResponse(db.Model):
    __tablename__ = 'review_responses'

    response_id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('reviews.review_id'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    response = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
