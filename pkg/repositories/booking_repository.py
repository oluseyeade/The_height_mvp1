from datetime import datetime
from sqlalchemy import or_, and_
from pkg.repositories.base_repository import BaseRepository
from pkg.models.booking import Booking
from pkg.models.availability import Availability

class BookingRepository(BaseRepository):
    def __init__(self):
        super().__init__(Booking)

    def find_by_ref(self, booking_ref):
        return Booking.query.filter_by(booking_ref=booking_ref.upper().strip()).first()

    def get_user_bookings(self, user_id):
        return Booking.query.filter_by(user_id=user_id).order_by(Booking.created_at.desc()).all()

    def check_date_availability(self, apartment_id, check_in_date, check_out_date):
        """
        Returns True if dates are available (no overlapping confirmed/pending bookings).
        """
        overlapping = Booking.query.filter(
            Booking.apartment_id == apartment_id,
            Booking.status.in_(['pending', 'confirmed', 'checked-in']),
            or_(
                and_(Booking.check_in <= check_in_date, Booking.check_out > check_in_date),
                and_(Booking.check_in < check_out_date, Booking.check_out >= check_out_date),
                and_(Booking.check_in >= check_in_date, Booking.check_out <= check_out_date)
            )
        ).first()
        return overlapping is None

class AvailabilityRepository(BaseRepository):
    def __init__(self):
        super().__init__(Availability)

    def get_apartment_calendar(self, apartment_id, start_date, end_date):
        return Availability.query.filter(
            Availability.apartment_id == apartment_id,
            Availability.date >= start_date,
            Availability.date <= end_date
        ).all()
