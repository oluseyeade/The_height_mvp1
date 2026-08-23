from pkg.repositories.review_repository import ReviewRepository
from pkg.repositories.booking_repository import BookingRepository
from pkg.models.review import Review, ReviewResponse
from pkg.services.audit_service import AuditService
from pkg.extensions import db

class ReviewService:
    def __init__(self):
        self.review_repo = ReviewRepository()
        self.booking_repo = BookingRepository()

    def submit_verified_review(self, booking_ref, rating, title, comment, user_id=None):
        booking = self.booking_repo.find_by_ref(booking_ref)
        if not booking:
            return False, "Invalid booking reference.", None

        # Rule 1: Only verified guests with a booking status of 'checked-out' or 'completed' may submit reviews.
        if booking.status not in ['checked-out', 'completed']:
            return False, "Review policy restriction: Reviews can only be submitted for completed stays.", None

        # Rule 2: Limit one review per completed booking.
        existing_review = self.review_repo.find_by_booking_id(booking.booking_id)
        if existing_review:
            return False, "Review policy restriction: A review has already been submitted for this booking.", None

        try:
            rating_val = int(rating)
            if rating_val < 1 or rating_val > 5:
                return False, "Rating must be between 1 and 5 stars.", None
        except ValueError:
            return False, "Invalid rating value.", None

        review = Review(
            booking_id=booking.booking_id,
            user_id=user_id or booking.user_id,
            apartment_id=booking.apartment_id,
            rating=rating_val,
            title=title.strip(),
            comment=comment.strip(),
            is_verified=True,  # "Verified Guest" badge flag
            is_public=True,
            status='approved'
        )

        self.review_repo.add(review)
        self.review_repo.commit()

        AuditService.log_activity(
            user_id=user_id or booking.user_id,
            activity_type='REVIEW_SUBMITTED',
            description=f"Verified review ({rating_val}/5 stars) submitted for booking {booking_ref}.",
            module='Review',
            action='submit'
        )

        return True, "Thank you! Your verified guest review has been published.", review

    def get_apartment_reviews(self, apartment_id):
        return self.review_repo.get_apartment_reviews(apartment_id)
