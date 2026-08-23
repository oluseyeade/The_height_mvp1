from datetime import datetime
from pkg.repositories.agent_repository import AgentRepository
from pkg.repositories.booking_repository import BookingRepository
from pkg.repositories.apartment_repository import ApartmentRepository
from pkg.models.booking import Booking
from pkg.services.audit_service import AuditService
from pkg.extensions import db

class BookingService:
    def __init__(self):
        self.booking_repo = BookingRepository()
        self.apt_repo = ApartmentRepository()
        self.agent_repo = AgentRepository()

    def _resolve_verified_agent_referral(self, agent_id=None, referral_code=None):
        candidate = None

        if agent_id:
            candidate = self.agent_repo.get_by_id(agent_id)
        elif referral_code:
            candidate = self.agent_repo.find_by_code(referral_code)

        if not candidate:
            return None

        if candidate.status != 'active':
            return None

        if not candidate.user or candidate.user.status != 'active':
            return None

        return candidate

    def create_booking_request(self, apartment_id, check_in_str, check_out_str, guest_count=1,
                              guest_name=None, guest_email=None, guest_phone=None,
                              user_id=None, agent_id=None, referral_code=None,
                              special_requests=None, source='website', allow_past=False):

        apt = self.apt_repo.get_by_id(apartment_id)
        if not apt:
            return False, "Selected apartment suite does not exist.", None

        if apt.status != 'available':
            return False, f"Apartment suite '{apt.title}' is currently unavailable.", None

        try:
            check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
            check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()
        except ValueError:
            return False, "Invalid check-in or check-out date format. Use YYYY-MM-DD.", None

        if check_in >= check_out:
            return False, "Check-out date must be after check-in date.", None

        if not allow_past and check_in < datetime.now().date():
            return False, "Check-in date cannot be in the past.", None

        # Check overlap
        if not self.booking_repo.check_date_availability(apartment_id, check_in, check_out):
            return False, "The apartment is already reserved for the selected dates. Please choose different dates.", None

        nights = (check_out - check_in).days
        total_price = apt.price_per_night * nights
        deposit_required = 50000.0  # Fixed ₦50,000 deposit requirement per policy

        verified_agent = self._resolve_verified_agent_referral(agent_id=agent_id, referral_code=referral_code)
        discount_amount = 0.0
        final_amount = total_price

        if verified_agent:
            discount_amount = round(total_price * 0.03, 2)
            final_amount = round(total_price - discount_amount, 2)
            agent_id = verified_agent.agent_id

        booking = Booking(
            apartment_id=apartment_id,
            user_id=user_id,
            agent_id=agent_id,
            booking_ref=Booking.generate_reference(),
            check_in=check_in,
            check_out=check_out,
            guest_count=int(guest_count),
            guest_name=guest_name.strip() if guest_name else None,
            guest_email=guest_email.lower().strip() if guest_email else None,
            guest_phone=guest_phone.strip() if guest_phone else None,
            price_per_night=apt.price_per_night,
            total_nights=nights,
            total_price=total_price,
            discount_amount=discount_amount,
            final_amount=final_amount,
            deposit_required=deposit_required,
            status='pending',
            source=source,
            special_requests=special_requests.strip() if special_requests else None
        )

        self.booking_repo.add(booking)
        self.booking_repo.commit()

        AuditService.log_activity(
            user_id=user_id,
            activity_type='BOOKING_REQUEST',
            description=f"Booking request {booking.booking_ref} created for apartment '{apt.title}'. Total: ₦{total_price:,.2f}",
            module='Booking',
            action='create'
        )

        return True, "Booking request submitted successfully. Please proceed with deposit payment.", booking

    def get_booking_by_ref(self, booking_ref):
        return self.booking_repo.find_by_ref(booking_ref)

    def get_user_bookings(self, user_id):
        return self.booking_repo.get_user_bookings(user_id)

    def get_all_bookings(self):
        return self.booking_repo.get_all()

    def update_booking_status(self, booking_id, new_status, admin_user_id=None):
        booking = self.booking_repo.get_by_id(booking_id)
        if not booking:
            return False, "Booking record not found."

        old_status = booking.status
        booking.status = new_status
        self.booking_repo.commit()

        if admin_user_id:
            AuditService.log_admin_action(
                admin_id=admin_user_id,
                target_user_id=booking.user_id,
                action_type='UPDATE_BOOKING_STATUS',
                previous_status=old_status,
                new_status=new_status,
                reason=f"Status of booking {booking.booking_ref} changed to {new_status}"
            )

        return True, f"Booking status updated to {new_status}."
