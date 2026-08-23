import os
import sys
from datetime import datetime, timedelta
sys.path.insert(0, os.getcwd())

from pkg import create_app
from pkg.extensions import db
from pkg.models.apartment import Apartment
from pkg.services.booking_service import BookingService
from pkg.services.payment_service import PaymentService
from pkg.seeds.seed_roles import seed_roles_and_superadmin
from pkg.seeds.seed_apartments import seed_default_apartments

app = create_app('testing')
with app.app_context():
    db.drop_all()
    db.create_all()
    seed_roles_and_superadmin()
    seed_default_apartments()

    booking_service = BookingService()
    payment_service = PaymentService()
    apt = Apartment.query.first()

    today = datetime.now().date()
    check_in = (today + timedelta(days=3)).strftime('%Y-%m-%d')
    check_out = (today + timedelta(days=6)).strftime('%Y-%m-%d')

    ok, msg, booking = booking_service.create_booking_request(
        apt.apartment_id,
        check_in,
        check_out,
        guest_name='Probe',
        guest_email='probe@example.com',
        guest_phone='08000000000'
    )
    print('BOOKING_OK', ok, msg, booking.booking_ref if booking else None)

    ok2, msg2, payment = payment_service.initialize_paystack_payment(
        booking_ref=booking.booking_ref,
        amount=50000.0,
        user_id=None,
        transaction_ref='PS-PROBE-1'
    )
    print('PAYMENT_INIT_OK', ok2, msg2, payment.payment_id if payment else None)

    ok3, msg3, receipt = payment_service.verify_paystack_payment('PS-PROBE-1')
    print('PAYMENT_VERIFY_OK', ok3, msg3, receipt.receipt_number if receipt else None)
