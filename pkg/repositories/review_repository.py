from pkg.repositories.base_repository import BaseRepository
from pkg.models.review import Review
from pkg.models.notification import Notification, EmailLog, WhatsAppLog

class ReviewRepository(BaseRepository):
    def __init__(self):
        super().__init__(Review)

    def find_by_booking_id(self, booking_id):
        return Review.query.filter_by(booking_id=booking_id).first()

    def get_apartment_reviews(self, apartment_id):
        return Review.query.filter_by(apartment_id=apartment_id, is_public=True, status='approved').order_by(Review.created_at.desc()).all()


class NotificationRepository(BaseRepository):
    def __init__(self):
        super().__init__(Notification)

    def get_user_notifications(self, user_id):
        return Notification.query.filter_by(user_id=user_id).order_by(Notification.created_at.desc()).all()
