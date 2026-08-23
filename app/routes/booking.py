from datetime import datetime
from flask import render_template, request, flash, redirect, url_for, jsonify, current_app
from flask_login import current_user
from app.services import ApartmentService, BookingService, PaymentService
from app.utils import get_booking_session, update_booking_session

apt_service = ApartmentService()
booking_service = BookingService()
payment_service = PaymentService()

def init_booking_routes(app):
    @app.route('/api/apartments/<int:apartment_id>/check-availability', endpoint='apartments.api_check_availability')
    def api_check_availability(apartment_id):
        apartment = apt_service.get_apartment_by_id(apartment_id)
        if not apartment or apartment.status != 'available':
            return jsonify({
                "success": False,
                "available": False,
                "message": "This apartment is not available. Please check other available apartments. Thank you."
            }), 409
        
        return jsonify({
            "success": True,
            "available": True,
            "message": "Apartment is available."
        }), 200

    @app.route('/bookings/create/<int:apartment_id>', methods=['GET', 'POST'], endpoint='bookings.create')
    def create_booking_route(apartment_id):
        apartment = apt_service.get_apartment_by_id(apartment_id)
        if not apartment:
            flash('Apartment not found.', 'danger')
            return redirect(url_for('apartments.list_apartments'))

        # Single Source of Truth DB Availability Validation
        if apartment.status != 'available':
            if request.is_json or request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    "success": False,
                    "available": False,
                    "message": "This apartment is currently unavailable. Please check our available apartments. Thank you."
                }), 409
            
            flash("This apartment is currently unavailable. Please check our available apartments. Thank you.", 'danger')
            return redirect(url_for('apartments.list_apartments'))

        b_session = update_booking_session(apartment=apartment)

        if request.method == 'POST':
            check_in_str = request.form.get('check_in') or b_session.get('check_in')
            check_out_str = request.form.get('check_out') or b_session.get('check_out')
            guest_name = request.form.get('guest_name', '').strip()
            guest_email = request.form.get('guest_email', '').strip()
            guest_phone = request.form.get('guest_phone', '').strip()
            guest_count = request.form.get('guest_count', b_session.get('number_of_guests', 1))
            special_requests = request.form.get('special_requests', '').strip()
            manual_ref = request.form.get('referral_code', '').strip()

            # Update session state with typed guest info and selected dates
            b_session = update_booking_session(
                check_in=check_in_str,
                check_out=check_out_str,
                guests=guest_count,
                apartment=apartment,
                manual_referral_code=manual_ref if manual_ref else None,
                guest_info={
                    'guest_name': guest_name,
                    'guest_email': guest_email,
                    'guest_phone': guest_phone,
                    'special_requests': special_requests
                }
            )

            # Server-Side Registration & Date Validation
            errors = []
            if not guest_name or len(guest_name) < 2:
                errors.append("Please enter your valid Full Name.")
            if not guest_email or '@' not in guest_email:
                errors.append("Please enter a valid Email Address.")
            if not guest_phone or len(guest_phone) < 7:
                errors.append("Please enter a valid Phone Number.")

            try:
                check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
                check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()
                if check_in >= check_out:
                    errors.append("Check-out date must be after check-in date.")
            except (ValueError, TypeError):
                errors.append("Invalid check-in or check-out date format.")

            # If validation fails: stay on page, preserve values, show errors, do NOT clear form
            if errors:
                for err in errors:
                    flash(err, 'danger')
                return redirect(url_for('apartments.detail', apartment_id=apartment_id))

            user_id = current_user.user_id if current_user.is_authenticated else None
            booking, msg = booking_service.create_booking(
                apartment_id=apartment_id,
                check_in_date=check_in,
                check_out_date=check_out,
                guest_name=guest_name,
                guest_email=guest_email,
                guest_phone=guest_phone,
                guest_count=b_session.get('number_of_guests', 1),
                user_id=user_id,
                referral_code=manual_ref if manual_ref else None,
                special_requests=special_requests,
                booking_token=b_session.get('booking_token')
            )

            if booking:
                b_session['booking_ref'] = booking.booking_ref
                flash(msg, 'success')
                return redirect(url_for('bookings.detail', booking_ref=booking.booking_ref))
            else:
                flash(msg, 'danger')
                return redirect(url_for('apartments.detail', apartment_id=apartment_id))

        return redirect(url_for('apartments.detail', apartment_id=apartment_id))

    @app.route('/bookings/detail/<booking_ref>', methods=['GET', 'POST'], endpoint='bookings.detail')
    def booking_detail(booking_ref):
        booking = booking_service.get_booking_by_ref(booking_ref)
        if not booking:
            flash('Booking reference not found.', 'danger')
            return redirect(url_for('apartments.list_apartments'))

        # Security Ownership Authorization Guard for Logged-In Customers
        if current_user.is_authenticated and not (getattr(current_user, 'is_admin', False) or getattr(current_user, 'is_superadmin', False)):
            if booking.user_id and booking.user_id != current_user.user_id and (booking.guest_email and booking.guest_email != current_user.email):
                flash('Access denied: You do not have permission to view this reservation.', 'danger')
                return redirect(url_for('auth.profile'))

        # Single Source of Truth DB Availability Protection
        if booking.apartment and booking.apartment.status != 'available':
            if request.is_json or request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    "success": False,
                    "available": False,
                    "message": "This apartment is currently unavailable. Please check our available apartments. Thank you."
                }), 409

            flash("This apartment is currently unavailable. Please check our available apartments. Thank you.", 'danger')
            return redirect(url_for('apartments.list_apartments'))

        b_session = get_booking_session()
        b_session['booking_ref'] = booking_ref

        # Dynamic Server-Side Pricing Calculations
        apt_booking_amount = float(booking.final_amount or booking.total_price)
        caution_fee = float(booking.caution_fee or 50000.00)
        total_payable_online = round(apt_booking_amount + caution_fee, 2)
        booking.total_amount = total_payable_online

        if request.method == 'POST':
            payment_method = request.form.get('payment_method', 'paystack')
            user_id = current_user.user_id if current_user.is_authenticated else None

            if payment_method == 'paystack':
                res, msg = payment_service.initialize_paystack_payment(booking_ref, user_id=user_id)
                if res and res.get('success'):
                    return redirect(res.get('authorization_url'))
                else:
                    flash(msg or "Failed to initialize Paystack checkout. Please try again.", 'danger')
                    return redirect(url_for('bookings.detail', booking_ref=booking_ref))
            else:
                deposit_amount = float(request.form.get('deposit_amount', total_payable_online))
                proof_file = request.files.get('payment_proof')
                payment, msg = payment_service.process_bank_transfer_deposit(
                    booking_id=booking.booking_id,
                    amount=deposit_amount,
                    proof_file=proof_file,
                    upload_folder=current_app.config['UPLOAD_FOLDER'],
                    user_id=user_id
                )

                if payment:
                    flash('Deposit proof uploaded successfully! Our Finance Officer will verify your payment.', 'success')
                    return redirect(url_for('bookings.detail', booking_ref=booking_ref))
                else:
                    flash(msg, 'danger')

        from app.models import Payment, Receipt
        latest_payment = Payment.query.filter_by(booking_id=booking.booking_id).order_by(Payment.created_at.desc()).first()
        receipt = Receipt.query.filter_by(payment_id=latest_payment.payment_id).first() if latest_payment else None

        return render_template('bookings/detail.html', 
                               booking=booking, 
                               apt_booking_amount=apt_booking_amount,
                               caution_fee=caution_fee,
                               total_payable_online=total_payable_online,
                               latest_payment=latest_payment,
                               receipt=receipt)

    @app.route('/bookings/api/summary/<booking_ref>', endpoint='bookings.api_summary')
    def api_summary(booking_ref):
        booking = booking_service.get_booking_by_ref(booking_ref)
        if not booking or (booking.apartment and booking.apartment.status != 'available'):
            return jsonify({
                "success": False,
                "available": False,
                "message": "This apartment is currently unavailable. Please check our available apartments. Thank you."
            }), 409

        original_amount = float(booking.total_price)
        discount_amount = float(booking.discount_amount or 0.0)
        amount_payable = float(booking.final_amount)
        caution_fee = float(booking.caution_fee or 50000.00)
        total_payable_online = round(amount_payable + caution_fee, 2)
        agent_commission = round(original_amount * 0.07, 2) if booking.agent_id else 0.0

        return jsonify({
            "booking_amount": original_amount,
            "customer_discount": discount_amount,
            "amount_payable": amount_payable,
            "caution_fee": caution_fee,
            "total_payable_online": total_payable_online,
            "agent_commission": agent_commission,
            "referral_applied": bool(booking.agent_id),
            "agent_id": booking.agent_id
        })

    @app.route('/bookings/success/<booking_ref>', endpoint='bookings.success')
    def booking_success(booking_ref):
        from app.models import Payment, Receipt
        booking = booking_service.get_booking_by_ref(booking_ref)
        if not booking:
            flash('Booking reference not found.', 'danger')
            return redirect(url_for('apartments.list_apartments'))

        # Mandatory Security Guard: Block access to success page if payment is not verified!
        is_verified = (
            booking.payment_status in ['VERIFIED', 'verified', 'SUCCESS', 'success'] or 
            booking.status in ['confirmed', 'CONFIRMED', 'active', 'ACTIVE']
        )
        if not is_verified:
            flash('Payment verification pending or incomplete. Please complete payment or check status.', 'warning')
            return redirect(url_for('bookings.detail', booking_ref=booking_ref))

        latest_payment = Payment.query.filter_by(booking_id=booking.booking_id).order_by(Payment.created_at.desc()).first()
        receipt = None
        if latest_payment:
            receipt = Receipt.query.filter_by(payment_id=latest_payment.payment_id).first()

        apt_booking_amount = float(booking.final_amount or booking.total_price)
        caution_fee = float(booking.caution_fee or 50000.00)
        total_paid = float(latest_payment.amount) if latest_payment else round(apt_booking_amount + caution_fee, 2)
        num_nights = (booking.check_out - booking.check_in).days if booking.check_in and booking.check_out else 1

        # Clear temporary referral & booking session data upon viewing success page
        from app.utils import clear_booking_session
        clear_booking_session()

        return render_template('bookings/success.html', 
                               booking=booking, 
                               payment=latest_payment, 
                               receipt=receipt,
                               apt_booking_amount=apt_booking_amount,
                               caution_fee=caution_fee,
                               total_paid=total_paid,
                               num_nights=num_nights)
