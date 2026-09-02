import os
import uuid
import json
import requests
import hashlib
from datetime import datetime, timedelta
from flask import has_request_context, session, current_app, url_for
from app.extensions import db
from app.models import User, Role, Agent, AgentCommission, Apartment, Category, Booking, Payment, Receipt, Availability

class UserService:
    def authenticate(self, email, password):
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            return user, "Authentication successful."
        return None, "Invalid email or password."

    def register_user(self, full_name, email, phone, password, role_name='Customer'):
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return None, "Email address is already registered."

        role = Role.query.filter_by(role_name=role_name).first()
        if not role:
            role = Role(role_name=role_name, hierarchy_level=1)
            db.session.add(role)
            db.session.commit()

        user = User(
            full_name=full_name,
            email=email,
            phone=phone,
            role_id=role.role_id,
            status='active'
        )
        user.set_password(password)

        db.session.add(user)
        db.session.commit()
        return user, "User registered successfully."

class ApartmentService:
    def get_all_active_apartments(self):
        return Apartment.query.filter_by(status='available').all()

    def get_featured_apartments(self, limit=4):
        from sqlalchemy.exc import DBAPIError, OperationalError, ProgrammingError
        try:
            return Apartment.query.filter_by(is_featured=True, status='available').limit(limit).all()
        except (ProgrammingError, OperationalError, DBAPIError) as e:
            err_str = str(e).lower()
            if '1146' in err_str or "doesn't exist" in err_str or 'no such table' in err_str:
                if has_request_context():
                    current_app.logger.warning(f"[DATABASE TABLE WARNING] 'apartments' table unavailable: {e}")
                else:
                    print(f"[DATABASE TABLE WARNING] 'apartments' table unavailable: {e}")
                db.session.rollback()
                return []
            raise

    def get_all_categories(self):
        return Category.query.filter_by(is_active=True).all()

    def get_apartment_by_id(self, apartment_id):
        return Apartment.query.get(apartment_id)

    def get_category_availability(self, category_id, check_in_date=None, check_out_date=None):
        """
        Calculates category availability based on physical unit inventory minus active reservations for the date range.
        """
        category = Category.query.get(category_id)
        if not category:
            return 0, []

        units = Apartment.query.filter_by(category_id=category_id, status='available').all()
        if not check_in_date or not check_out_date:
            return len(units), units

        free_units = []
        for u in units:
            overlap = Booking.query.filter(
                Booking.apartment_id == u.apartment_id,
                Booking.status.in_(['CONFIRMED', 'confirmed', 'CHECKED_IN', 'checked_in', 'pending', 'ACTIVE', 'active']),
                Booking.check_in < check_out_date,
                Booking.check_out > check_in_date
            ).first()
            if not overlap:
                free_units.append(u)

        return len(free_units), free_units

    def get_category_showcase(self, check_in_date=None, check_out_date=None):
        categories = Category.query.filter_by(is_active=True).order_by(Category.sort_order).all()
        showcase = []
        for cat in categories:
            units = Apartment.query.filter_by(category_id=cat.category_id, status='available').all()
            if not units:
                continue
            primary_unit = units[0]
            avail_count, free_units = self.get_category_availability(cat.category_id, check_in_date, check_out_date)
            showcase.append({
                'category_id': cat.category_id,
                'name': cat.name,
                'description': primary_unit.description,
                'price_per_night': primary_unit.price_per_night,
                'bedrooms': primary_unit.bedrooms,
                'bathrooms': primary_unit.bathrooms,
                'capacity': primary_unit.capacity,
                'cover_image': primary_unit.cover_image,
                'apartment_id': primary_unit.apartment_id,
                'display_title': primary_unit.display_title,
                'total_units': len(units),
                'available_units_count': avail_count,
                'is_available': avail_count > 0,
                'apartment': primary_unit
            })
        return showcase

    def add_apartment_image(self, apartment_id, image_url, user_id=None, is_cover=False, caption=None):
        apartment = Apartment.query.get(apartment_id)
        if not apartment:
            return None, "Apartment not found."

        from app.models import ApartmentImage
        if is_cover:
            ApartmentImage.query.filter_by(apartment_id=apartment_id).update({'is_cover': False})

        count = ApartmentImage.query.filter_by(apartment_id=apartment_id).count()
        img = ApartmentImage(
            apartment_id=apartment_id,
            uploaded_by=user_id,
            image_url=image_url,
            is_cover=is_cover or (count == 0),
            caption=caption,
            sort_order=count + 1
        )
        db.session.add(img)
        db.session.commit()
        return img, "Image added successfully."

    def delete_apartment_image(self, image_id):
        from app.models import ApartmentImage
        img = ApartmentImage.query.get(image_id)
        if not img:
            return False, "Image not found."

        apt_id = img.apartment_id
        was_cover = img.is_cover

        try:
            if img.image_url.startswith('uploads/'):
                full_path = os.path.join(current_app.root_path, 'static', img.image_url)
                if os.path.exists(full_path):
                    os.remove(full_path)
        except Exception:
            pass

        db.session.delete(img)
        db.session.commit()

        if was_cover:
            remaining = ApartmentImage.query.filter_by(apartment_id=apt_id).first()
            if remaining:
                remaining.is_cover = True
                db.session.commit()

        return True, "Image deleted successfully."

    def set_cover_image(self, image_id):
        from app.models import ApartmentImage
        target_img = ApartmentImage.query.get(image_id)
        if not target_img:
            return False, "Image not found."

        ApartmentImage.query.filter_by(apartment_id=target_img.apartment_id).update({'is_cover': False})
        target_img.is_cover = True
        db.session.commit()
        return True, "Cover image set successfully."

    def update_apartment_price(self, apartment_id, new_price):
        apartment = Apartment.query.get(apartment_id)
        if not apartment:
            return None, "Apartment not found."

        try:
            price_val = float(new_price)
            if price_val <= 0:
                return None, "Price must be a positive numeric value greater than zero."
        except (ValueError, TypeError):
            return None, "Invalid price format. Must be a numeric value."

        apartment.price_per_night = price_val
        db.session.commit()
        return apartment, f"Price for '{apartment.title}' updated successfully to ₦{price_val:,.2f} per night."

class BookingService:
    def expire_stale_pending_bookings(self, timeout_minutes=30):
        cutoff_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)
        stale_bookings = Booking.query.filter(
            Booking.status == 'pending',
            Booking.created_at < cutoff_time
        ).all()

        for b in stale_bookings:
            b.status = 'EXPIRED'
            b.booking_status = 'EXPIRED'
            b.payment_status = 'TIMED_OUT'

        if stale_bookings:
            db.session.commit()

    def create_booking(self, apartment_id, check_in_date, check_out_date, guest_name, guest_email, guest_phone, guest_count=1, user_id=None, agent_id=None, referral_code=None, special_requests=None, source='website', booking_token=None):
        self.expire_stale_pending_bookings(timeout_minutes=30)
        target_apartment = Apartment.query.get(apartment_id)
        if not target_apartment:
            return None, "Selected apartment does not exist."

        if check_in_date >= check_out_date:
            return None, "Check-out date must be after check-in date."

        from app.models import Booking

        # Category Physical-Unit Allocation Strategy with Transaction Lock
        # Find all physical units in this apartment category
        category_units = Apartment.query.filter_by(category_id=target_apartment.category_id, status='available').with_for_update().all()
        if not category_units:
            return None, "No active physical units available in this category."

        def check_unit_free(unit_id):
            overlap = Booking.query.filter(
                Booking.apartment_id == unit_id,
                Booking.status.in_(['CONFIRMED', 'confirmed', 'CHECKED_IN', 'checked_in', 'pending', 'ACTIVE', 'active']),
                Booking.check_in < check_out_date,
                Booking.check_out > check_in_date
            ).first()
            if overlap and overlap.guest_email == guest_email and overlap.status == 'pending':
                return True, overlap
            return overlap is None, None

        assigned_unit = None
        reusable_booking = None

        # 1. Prefer requested physical unit if free
        is_free, existing_pend = check_unit_free(target_apartment.apartment_id)
        if existing_pend:
            reusable_booking = existing_pend
            assigned_unit = target_apartment
        elif is_free:
            assigned_unit = target_apartment
        else:
            # 2. Automatically find and assign available sister physical unit in the same category
            for sister_unit in category_units:
                free, pend = check_unit_free(sister_unit.apartment_id)
                if pend:
                    reusable_booking = pend
                    assigned_unit = sister_unit
                    break
                elif free:
                    assigned_unit = sister_unit
                    break

        if not assigned_unit:
            return None, "All units in this apartment category are fully booked for your selected dates. Please choose different dates."

        apartment = assigned_unit
        apartment_id = assigned_unit.apartment_id

        if reusable_booking:
            return reusable_booking, "Existing pending reservation retrieved successfully."

        num_nights = (check_out_date - check_in_date).days
        original_price = float(apartment.price_per_night) * num_nights

        # Idempotency check: if existing pending booking exists for this guest & apartment & dates, reuse it
        existing_booking = Booking.query.filter_by(
            apartment_id=apartment_id,
            guest_email=guest_email,
            check_in=check_in_date,
            check_out=check_out_date,
            status='pending'
        ).order_by(Booking.created_at.desc()).first()

        if existing_booking:
            return existing_booking, "Existing pending reservation retrieved successfully."

        # Server-side Referral Validation & Discount Engine (Strict Referral Flow)
        from app.utils import validate_referral_code
        if referral_code == "":
            ref_code = None
        elif referral_code:
            ref_code = referral_code
        else:
            ref_code = session.get('referral_code') if has_request_context() else None

        active_agent, is_valid_ref, val_msg = validate_referral_code(ref_code, customer_user_id=user_id, customer_email=guest_email)

        if is_valid_ref and active_agent:
            discount_pct = 3.00
            discount_amount = round(original_price * 0.03, 2)
            final_amount = round(original_price - discount_amount, 2)
            assigned_agent_id = active_agent.agent_id
            booking_source = 'agent'
            msg = f"Booking request created successfully with 3% Agent Referral Discount! (Saved ₦{discount_amount:,.2f}). Please note that a refundable ₦50,000 caution fee is included in your payment and will be refunded after checkout, subject to the applicable terms and conditions."
        else:
            ref_code = None
            active_agent = None
            is_valid_ref = False
            discount_pct = 0.00
            discount_amount = 0.00
            final_amount = original_price
            assigned_agent_id = None
            booking_source = source
            msg = "Booking request created successfully. Please note that a refundable ₦50,000 caution fee is included in your payment and will be refunded after checkout, subject to the applicable terms and conditions."

        # Defensive Forensic Logging
        if has_request_context():
            from flask import request
            print("=" * 60)
            print("Request Args:", request.args)
            print("Form Data:", request.form)
            print("Hidden Referral:", request.form.get('referral_code'))
            print("Referral Code:", ref_code)
            print("Agent ID:", assigned_agent_id)
            print("=" * 60)

        print(f"verified_agent: {active_agent}")
        print(f"discount_amount: {discount_amount}")
        print(f"booking.agent_id: {assigned_agent_id}")
        print(f"booking.final_amount: {final_amount}")

        booking_ref = f"THA-{uuid.uuid4().hex[:8].upper()}"
        caution_fee_val = 50000.00
        grand_total = round(final_amount + caution_fee_val, 2)

        booking = Booking(
            user_id=user_id,
            apartment_id=apartment_id,
            agent_id=assigned_agent_id,
            check_in=check_in_date,
            check_out=check_out_date,
            guest_count=guest_count,
            total_price=original_price,
            discount_amount=discount_amount,
            final_amount=final_amount,
            caution_fee_amount=caution_fee_val,
            caution_fee=caution_fee_val,
            apartment_fee=original_price,
            discount_percentage=discount_pct,
            total_amount=grand_total,
            payment_status='PENDING_PAYMENT',
            booking_status='Pending Payment',
            refund_status='NOT_APPLICABLE',
            booking_ref=booking_ref,
            status='pending',
            guest_name=guest_name,
            guest_email=guest_email,
            guest_phone=guest_phone,
            special_requests=special_requests,
            source=booking_source
        )

        db.session.add(booking)
        db.session.commit()

        # Trigger SuperAdmin Notification for New Booking
        NotificationService.create_notification(
            notification_type='BOOKING_CREATED',
            portal='BOOKINGS',
            title='New Booking Created',
            message=f"Booking #{booking_ref} created for {guest_name}.",
            priority='MEDIUM',
            requires_action=False,
            related_type='Booking',
            related_id=booking.booking_id,
            action_url='/admin/bookings'
        )

        return booking, msg

    def get_booking_by_ref(self, booking_ref):
        return Booking.query.filter_by(booking_ref=booking_ref).first()

    def get_user_bookings(self, user_id):
        return Booking.query.filter_by(user_id=user_id).order_by(Booking.created_at.desc()).all()

class PaymentService:
    def initialize_paystack_payment(self, booking_ref, user_id=None):
        booking = Booking.query.filter_by(booking_ref=booking_ref).first()
        if not booking:
            return None, "Booking record not found."
        
        if booking.status in ['confirmed', 'CONFIRMED', 'active', 'ACTIVE']:
            return None, "This reservation is already confirmed and active."

        # Date availability check: prevent double booking against active confirmed reservations
        active_overlap = Booking.query.filter(
            Booking.apartment_id == booking.apartment_id,
            Booking.booking_id != booking.booking_id,
            Booking.status.in_(['confirmed', 'CONFIRMED', 'active', 'ACTIVE']),
            Booking.check_in < booking.check_out,
            Booking.check_out > booking.check_in
        ).first()

        if active_overlap:
            return None, "Selected dates are no longer available. Please select different dates."

        # Dynamic Payment Calculation: Apartment Booking Amount + Refundable Caution Fee (₦50,000)
        apt_amount = float(booking.final_amount or booking.total_price or 0.0)
        caution_fee = float(booking.caution_fee or 50000.00)
        total_payable = round(apt_amount + caution_fee, 2)
        booking.total_amount = total_payable

        tx_ref = f"PAY-THA-{uuid.uuid4().hex[:8].upper()}"

        # Prevent duplicate initialization by updating or creating pending payment
        payment = Payment.query.filter_by(booking_id=booking.booking_id, status='pending').first()
        if not payment:
            payment = Payment(
                booking_id=booking.booking_id,
                user_id=user_id or booking.user_id,
                amount=total_payable,
                payment_method='paystack',
                transaction_ref=tx_ref,
                paystack_reference=tx_ref,
                status='pending',
                payment_channel='card',
                payment_gateway='paystack',
                verification_status='pending'
            )
            db.session.add(payment)
        else:
            payment.amount = total_payable
            payment.transaction_ref = tx_ref
            payment.paystack_reference = tx_ref
            payment.status = 'pending'
            payment.verification_status = 'pending'
        
        db.session.commit()

        # Build Paystack API Request Payload
        secret_key = (current_app.config.get('PAYSTACK_SECRET_KEY') or '').strip()
        kobo_amount = int(round(total_payable * 100))
        
        configured_callback = current_app.config.get('PAYSTACK_CALLBACK_URL')
        if configured_callback and not configured_callback.endswith('_mock') and configured_callback.startswith('http'):
            callback_url = f"{configured_callback}?reference={tx_ref}" if '?' not in configured_callback else f"{configured_callback}&reference={tx_ref}"
        elif has_request_context():
            callback_url = url_for('payments.paystack_callback', reference=tx_ref, _external=True)
        else:
            callback_url = f"http://127.0.0.1:5050/payments/paystack/callback?reference={tx_ref}"
        
        payload = {
            "email": booking.guest_email or "guest@theheightapts.com",
            "amount": kobo_amount,
            "currency": "NGN",
            "reference": tx_ref,
            "callback_url": callback_url,
            "metadata": {
                "booking_ref": booking.booking_ref,
                "booking_id": booking.booking_id,
                "payment_id": payment.payment_id,
                "apartment_id": booking.apartment_id,
                "customer_id": booking.user_id,
                "apartment_fee": apt_amount,
                "caution_fee": caution_fee,
                "total_payable": total_payable,
                "custom_fields": [
                    {
                        "display_name": "Booking Reference",
                        "variable_name": "booking_ref",
                        "value": booking.booking_ref
                    },
                    {
                        "display_name": "Guest Name",
                        "variable_name": "guest_name",
                        "value": booking.guest_name or ""
                    }
                ]
            }
        }

        req_id = uuid.uuid4().hex[:6].upper()
        current_app.logger.info(f"[PAYSTACK_INIT_START] request_id={req_id} booking={booking.booking_ref} paystack_ref={tx_ref} endpoint=/transaction/initialize secret_key_fingerprint={hashlib.sha256(secret_key.encode()).hexdigest()[:8]}")

        init_url = current_app.config.get('PAYSTACK_INITIALIZE_URL', 'https://api.paystack.co/transaction/initialize')

        # If Paystack secret key configured, call Paystack REST Initialize API
        if secret_key and secret_key.startswith('sk_'):
            headers = {
                "Authorization": f"Bearer {secret_key}",
                "Content-Type": "application/json"
            }
            try:
                resp = requests.post(init_url, json=payload, headers=headers, timeout=10)
                res_data = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {}
                api_status = bool(res_data.get('status'))
                auth_url = res_data.get('data', {}).get('authorization_url') if api_status else None
                err_msg = res_data.get('message', f'Paystack REST API returned HTTP {resp.status_code}')

                current_app.logger.info(
                    f"[PAYSTACK_INIT_RESPONSE] request_id={req_id} http_status={resp.status_code} paystack_status={api_status} message='{err_msg}' authorization_url_present={bool(auth_url)}"
                )

                if resp.status_code == 200 and api_status and auth_url:
                    return {
                        "success": True,
                        "authorization_url": auth_url,
                        "reference": tx_ref,
                        "amount": total_payable
                    }, "Paystack payment initialized successfully."
                else:
                    current_app.logger.error(f"[PAYSTACK_INIT_ERROR] request_id={req_id} API Initialization Error: {err_msg}")
                    return {
                        "success": False,
                        "authorization_url": None,
                        "reference": tx_ref,
                        "amount": total_payable,
                        "error": err_msg
                    }, f"Paystack payment initialization failed: {err_msg}"
            except Exception as e:
                current_app.logger.error(f"[PAYSTACK_INIT_EXCEPTION] request_id={req_id} Exception: {str(e)}")
                return {
                    "success": False,
                    "authorization_url": None,
                    "reference": tx_ref,
                    "amount": total_payable,
                    "error": str(e)
                }, f"Paystack API connection error: {str(e)}"

        # Fallback redirect URL for offline local test environments
        return {
            "success": True,
            "authorization_url": callback_url,
            "reference": tx_ref,
            "amount": total_payable
        }, "Paystack payment initialized successfully."

    def verify_paystack_payment(self, reference):
        if not reference or not str(reference).strip():
            return False, None, "Invalid or missing transaction reference."

        reference = str(reference).strip()

        payment = Payment.query.filter(
            (Payment.transaction_ref == reference) | (Payment.paystack_reference == reference)
        ).first()

        if not payment:
            return False, None, "Payment transaction reference not found in database."

        booking = payment.booking
        if not booking:
            return False, None, "Associated reservation not found."

        # Idempotency Check: Prevent duplicate processing if payment already verified
        if payment.status in ['verified', 'SUCCESS'] and booking.status in ['confirmed', 'CONFIRMED', 'active', 'ACTIVE']:
            return True, booking, "Payment already verified successfully (idempotent)."

        expected_total = float(payment.amount or booking.total_amount or (float(booking.final_amount or 0) + float(booking.caution_fee or 50000)))
        expected_kobo = int(round(expected_total * 100))

        current_app.logger.info(f"[PAYSTACK] Callback received")
        current_app.logger.info(f"[PAYSTACK] Booking reference: {booking.booking_ref}")
        current_app.logger.info(f"[PAYSTACK] Paystack reference: {reference}")
        current_app.logger.info(f"[PAYSTACK] Expected booking amount: ₦{expected_total:,.2f}")
        current_app.logger.info(f"[PAYSTACK] Expected amount in kobo: {expected_kobo} kobo")

        secret_key = (current_app.config.get('PAYSTACK_SECRET_KEY') or '').strip()
        verify_base_url = current_app.config.get('PAYSTACK_VERIFY_URL', 'https://api.paystack.co/transaction/verify')
        is_valid_paystack = False
        failure_reason = "Paystack verification failed: Unknown error."

        if not secret_key:
            current_app.logger.error(f"[PAYSTACK] Error: PAYSTACK_SECRET_KEY is missing in configuration.")
            return False, booking, "Paystack verification failed: Secret key configuration missing."

        headers = {"Authorization": f"Bearer {secret_key}"}
        try:
            verify_url = f"{verify_base_url}/{reference}"
            current_app.logger.info(f"[PAYSTACK] Calling verification API: {verify_url}")
            resp = requests.get(verify_url, headers=headers, timeout=10)
            current_app.logger.info(f"[PAYSTACK] Verification HTTP status: {resp.status_code}")

            if resp.status_code == 200:
                paystack_res_data = resp.json()
                api_status = paystack_res_data.get('status')
                tx_data = paystack_res_data.get('data', {}) if api_status else {}

                tx_status = str(tx_data.get('status', '')).lower()
                paid_kobo = int(tx_data.get('amount', 0))
                paid_currency = str(tx_data.get('currency', 'NGN')).upper()

                current_app.logger.info(f"[PAYSTACK] Paystack transaction status: {tx_status}")
                current_app.logger.info(f"[PAYSTACK] Paystack returned amount: {paid_kobo} kobo")
                current_app.logger.info(f"[PAYSTACK] Paystack returned currency: {paid_currency}")

                if api_status is True and tx_status in ['success', 'successful'] and paid_kobo == expected_kobo and paid_currency == 'NGN':
                    is_valid_paystack = True
                    failure_reason = ""
                elif tx_status not in ['success', 'successful']:
                    failure_reason = f"Paystack verification failed: transaction status is '{tx_status}' (expected 'success')."
                elif paid_kobo != expected_kobo:
                    failure_reason = f"Paystack verification failed: amount mismatch. Expected {expected_kobo:,} kobo; Paystack returned {paid_kobo:,} kobo."
                elif paid_currency != 'NGN':
                    failure_reason = f"Paystack verification failed: currency mismatch. Expected NGN; Paystack returned {paid_currency}."
                else:
                    failure_reason = f"Paystack verification failed: API response status is false."
            else:
                err_body = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {}
                err_msg = err_body.get('message', f'HTTP {resp.status_code}')
                failure_reason = f"Paystack verification failed: Paystack API returned HTTP {resp.status_code} ({err_msg})."
                current_app.logger.error(f"[PAYSTACK] {failure_reason}")
        except Exception as e:
            failure_reason = f"Paystack verification failed: Paystack API connection error ({str(e)})."
            current_app.logger.error(f"[PAYSTACK] {failure_reason}")

        if not is_valid_paystack:
            payment.status = 'failed'
            payment.verification_status = 'failed'
            booking.status = 'pending'
            booking.payment_status = 'PAYMENT_FAILED'
            db.session.commit()

            NotificationService.create_notification(
                notification_type='PAYMENT_FAILED',
                portal='BOOKINGS',
                title='Payment Verification Failed',
                message=f"Payment attempt for Booking #{booking.booking_ref} failed: {failure_reason}",
                priority='HIGH',
                requires_action=True,
                related_type='Booking',
                related_id=booking.booking_id,
                action_url='/admin/bookings'
            )
            return False, booking, failure_reason

        current_app.logger.info(f"[PAYSTACK] Booking #{booking.booking_ref} marked PAID")

        # Atomic Transaction Execution for Reservation Activation & Date Blocking
        try:
            with db.session.begin_nested():
                # Mark Payment SUCCESS / verified
                payment.status = 'verified'
                payment.verification_status = 'verified'
                payment.verified_at = datetime.utcnow()
                if paystack_res_data:
                    payment.callback_payload = json.dumps(paystack_res_data)

                # Mark Reservation ACTIVE / CONFIRMED
                booking.status = 'confirmed'
                booking.booking_status = 'CONFIRMED'
                booking.payment_status = 'VERIFIED'
                booking.payment_reference = reference
                booking.verified_at = datetime.utcnow()

                # Block selected dates on Availability calendar
                current_date = booking.check_in
                while current_date < booking.check_out:
                    avail = Availability.query.filter_by(
                        apartment_id=booking.apartment_id,
                        date=current_date
                    ).first()
                    if not avail:
                        avail = Availability(
                            apartment_id=booking.apartment_id,
                            date=current_date,
                            status='booked'
                        )
                        db.session.add(avail)
                    else:
                        avail.status = 'booked'
                    current_date += timedelta(days=1)

                # Record Enterprise Commission (on Apartment Booking Fee ONLY, excluding Caution Fee)
                if booking.agent_id:
                    from app.services import CommissionService
                    CommissionService.generate_commission_for_booking(
                        booking_id=booking.booking_id,
                        payment_reference=reference
                    )

                # Idempotent Receipt Generation
                existing_receipt = Receipt.query.filter_by(payment_id=payment.payment_id).first()
                if not existing_receipt:
                    receipt = Receipt(
                        payment_id=payment.payment_id,
                        receipt_number=f"RCP-THA-{uuid.uuid4().hex[:6].upper()}",
                        generated_at=datetime.utcnow()
                    )
                    db.session.add(receipt)

            db.session.commit()

            NotificationService.create_notification(
                notification_type='PAYMENT_VERIFIED',
                portal='BOOKINGS',
                title='Payment Successfully Verified',
                message=f"Payment for Booking #{booking.booking_ref} verified (₦{expected_total:,.2f}).",
                priority='MEDIUM',
                requires_action=False,
                related_type='Booking',
                related_id=booking.booking_id,
                action_url='/admin/bookings'
            )

            # Clear temporary session data
            from app.utils import clear_booking_session
            clear_booking_session()

            return True, booking, "Reservation activated, calendar dates blocked, and receipt generated!"
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error activating booking for reference {reference}: {str(e)}")
            return False, booking, f"Database transaction error during activation: {str(e)}"

    def process_bank_transfer_deposit(self, booking_id, amount, proof_file, upload_folder, user_id=None):
        booking = Booking.query.get(booking_id)
        if not booking:
            return None, "Booking record not found."

        proof_path = None
        if proof_file and proof_file.filename:
            os.makedirs(upload_folder, exist_ok=True)
            filename = f"proof_{booking.booking_ref}_{uuid.uuid4().hex[:6]}.png"
            proof_path = os.path.join('uploads', filename)
            abs_path = os.path.join(upload_folder, filename)
            proof_file.save(abs_path)

        tx_ref = f"TXN-{uuid.uuid4().hex[:10].upper()}"

        payment = Payment(
            booking_id=booking_id,
            user_id=user_id,
            amount=amount,
            payment_method='bank_transfer',
            transaction_ref=tx_ref,
            payment_proof_path=proof_path,
            status='pending',
            payment_channel='bank_transfer',
            payment_gateway='paystack',
            verification_status='pending'
        )

        db.session.add(payment)
        db.session.commit()

        return payment, "Bank transfer deposit submitted successfully. Verification pending."

    def verify_payment(self, payment_id, verified_by_user_id):
        payment = Payment.query.get(payment_id)
        if not payment:
            return False, "Payment record not found."

        payment.status = 'verified'
        payment.verification_status = 'verified'
        payment.verified_by = verified_by_user_id
        payment.verified_at = datetime.utcnow()

        if payment.booking:
            booking = payment.booking
            booking.status = 'confirmed'
            booking.booking_status = 'CONFIRMED'
            booking.payment_status = 'VERIFIED'
            booking.verified_at = datetime.utcnow()

            # Idempotent Agent Commission Recording (Apartment Fee ONLY)
            if booking.agent_id:
                from app.services import CommissionService
                CommissionService.generate_commission_for_booking(
                    booking_id=booking.booking_id,
                    payment_reference=payment.transaction_ref or payment.paystack_reference or f"TXN-{booking.booking_ref}"
                )

        # Idempotent Receipt Generation
        existing_receipt = Receipt.query.filter_by(payment_id=payment.payment_id).first()
        if not existing_receipt:
            receipt_num = f"RCP-THA-{uuid.uuid4().hex[:6].upper()}"
            receipt = Receipt(
                payment_id=payment.payment_id,
                receipt_number=receipt_num,
                generated_at=datetime.utcnow()
            )
            db.session.add(receipt)
        else:
            receipt_num = existing_receipt.receipt_number

        db.session.commit()

        # Clear temporary booking session only after successful payment verification
        from app.utils import clear_booking_session
        clear_booking_session()

        return True, f"Payment verified successfully. Branded Receipt #{receipt_num} generated."

class InspectionService:
    def create_inspection(self, booking_id, inspector_id, data):
        from app.models import Inspection, Booking
        booking = Booking.query.get(booking_id)
        if not booking:
            return None, "Booking not found."

        damage_found = bool(data.get('damage_found', False))
        est_cost = float(data.get('estimated_repair_cost', 0.00))

        inspection = Inspection(
            booking_id=booking_id,
            inspector_id=inspector_id,
            property_condition=data.get('property_condition', 'excellent'),
            furniture_status=data.get('furniture_status', 'good'),
            electronics_status=data.get('electronics_status', 'good'),
            kitchen_status=data.get('kitchen_status', 'good'),
            bathroom_status=data.get('bathroom_status', 'good'),
            keys_status=data.get('keys_status', 'returned'),
            remotes_status=data.get('remotes_status', 'returned'),
            damage_found=damage_found,
            damage_description=data.get('damage_description', ''),
            estimated_repair_cost=est_cost,
            recommendation=data.get('recommendation', 'full_refund' if not damage_found else 'partial_refund'),
            approval_status='pending'
        )

        booking.inspection_status = 'INSPECTED_DAMAGES' if damage_found else 'INSPECTED_CLEAN'
        booking.refund_status = 'PENDING_INSPECTION_REVIEW'

        db.session.add(inspection)
        db.session.commit()
        return inspection, "Inspection report filed successfully."

class RefundService:
    def create_refund_request(self, booking_id, admin_user_id, refund_type, amount, reason, notes=""):
        from app.models import Refund, Booking
        booking = Booking.query.get(booking_id)
        if not booking:
            return None, "Booking not found."

        refund = Refund(
            booking_id=booking_id,
            approved_by=admin_user_id,
            refund_amount=amount,
            refund_reason=reason,
            refund_type=refund_type,
            refund_status='processed',
            processed_at=datetime.utcnow(),
            notes=notes
        )

        booking.refund_status = f"REFUND_{refund_type.upper()}"
        booking.caution_fee_status = 'Refund Processed'

        db.session.add(refund)
        db.session.commit()

        return refund, f"Manual {refund_type.capitalize()} Refund of ₦{amount:,.2f} recorded permanently."


class CommissionService:
    """
    Enterprise Commission Service managing referral entitlements, approvals, payouts, audit logging, and reporting.
    """

    @staticmethod
    def generate_commission_for_booking(booking_id, payment_reference, ip_address=None, user_agent=None):
        """
        Creates an enterprise Commission record for a verified booking.
        Enforces idempotency and row-level nested transaction integrity.
        Formula: Commission = Apartment Fee * 7.00%
        """
        from app.models import Booking, Commission, CommissionAuditLog, Agent, AgentCommission
        from app.extensions import db

        booking = Booking.query.get(booking_id)
        if not booking or not booking.agent_id:
            return None, "Booking is not associated with any agent."

        # Unique Check
        existing = Commission.query.filter(
            (Commission.booking_id == booking.booking_id) | 
            (Commission.payment_reference == payment_reference)
        ).first()
        if existing:
            return existing, "Commission record already exists."

        # Original apartment fee before discount
        orig_amount = float(booking.total_price or booking.final_amount or 0.0)
        disc_pct = float(booking.discount_percentage or 3.00)
        disc_amt = float(booking.discount_amount or 0.0)
        net_amt = float(booking.final_amount or orig_amount)
        comm_pct = 7.00
        comm_amount = round(orig_amount * 0.07, 2)

        comm_ref = f"COM-THA-{uuid.uuid4().hex[:8].upper()}"

        commission = Commission(
            commission_reference=comm_ref,
            booking_id=booking.booking_id,
            agent_id=booking.agent_id,
            referral_code=booking.agent.agent_code if booking.agent else '',
            customer_id=booking.user_id,
            property_id=booking.apartment.property_id if booking.apartment else None,
            payment_reference=payment_reference,
            payment_provider='PAYSTACK',
            booking_amount=orig_amount,
            discount_percentage=disc_pct,
            discount_amount=disc_amt,
            net_booking_amount=net_amt,
            commission_percentage=comm_pct,
            commission_amount=comm_amount,
            currency='NGN',
            commission_status='PENDING',
            payment_status='PENDING',
            commission_type='REFERRAL',
            generated_at=datetime.utcnow()
        )
        db.session.add(commission)
        db.session.flush()

        # Update Booking link
        booking.commission_generated = True
        booking.commission_id = commission.commission_id

        # Update Agent pending earnings
        if booking.agent:
            booking.agent.pending_commission = float(booking.agent.pending_commission or 0) + comm_amount

        # Create Immutable Audit Log
        audit = CommissionAuditLog(
            commission_id=commission.commission_id,
            action='CREATED',
            old_status=None,
            new_status='PENDING',
            performed_by=None,
            ip_address=ip_address,
            device=user_agent,
            remarks='Enterprise referral commission generated upon Paystack payment verification.'
        )
        db.session.add(audit)

        # Legacy AgentCommission backward compatibility
        legacy_comm = AgentCommission.query.filter_by(booking_id=booking.booking_id).first()
        if not legacy_comm:
            db.session.add(AgentCommission(
                agent_id=booking.agent_id,
                booking_id=booking.booking_id,
                booking_amount=orig_amount,
                commission_percentage=comm_pct,
                commission_rate=comm_pct,
                commission_amount=comm_amount,
                payment_status='verified',
                payment_verified=True,
                payout_status='pending',
                payment_reference=payment_reference
            ))

        return commission, "Commission generated successfully."

    @staticmethod
    def update_commission_status(commission_id, new_status, performed_by_user_id=None, remarks=None, ip_address=None, device=None):
        """
        Updates commission status (PENDING -> APPROVED -> PROCESSING -> PAID / CANCELLED / REVERSED) and writes an immutable audit record.
        """
        from app.models import Commission, CommissionAuditLog
        from app.extensions import db

        comm = Commission.query.get(commission_id)
        if not comm:
            return False, "Commission record not found."

        old_status = comm.commission_status
        new_status = new_status.upper().strip()

        if old_status == new_status:
            return True, f"Commission is already in status {new_status}."

        comm.commission_status = new_status
        comm.updated_at = datetime.utcnow()

        if new_status == 'APPROVED':
            comm.approved_at = datetime.utcnow()
            comm.approved_by = performed_by_user_id
        elif new_status == 'PAID':
            comm.paid_at = datetime.utcnow()
            comm.payment_status = 'SUCCESS'
            if comm.agent:
                comm.agent.pending_commission = max(0.0, float(comm.agent.pending_commission or 0) - float(comm.commission_amount))
                comm.agent.total_earnings = float(comm.agent.total_earnings or 0) + float(comm.commission_amount)
        elif new_status in ['CANCELLED', 'REVERSED', 'FAILED']:
            comm.cancelled_at = datetime.utcnow()
            if old_status in ['PENDING', 'APPROVED'] and comm.agent:
                comm.agent.pending_commission = max(0.0, float(comm.agent.pending_commission or 0) - float(comm.commission_amount))

        audit = CommissionAuditLog(
            commission_id=comm.commission_id,
            action=f"STATUS_CHANGE_{new_status}",
            old_status=old_status,
            new_status=new_status,
            performed_by=performed_by_user_id,
            ip_address=ip_address,
            device=device,
            remarks=remarks or f"Commission status updated from {old_status} to {new_status}."
        )
        db.session.add(audit)
        db.session.commit()
        return True, f"Commission status successfully updated to {new_status}."

    @staticmethod
    def create_manual_commission(agent_id, amount, commission_type='BONUS', notes=None, performed_by_user_id=None):
        """
        Creates a manual bonus or adjustment commission for an agent.
        """
        from app.models import Commission, CommissionAuditLog, Agent
        from app.extensions import db

        agent = Agent.query.get(agent_id)
        if not agent:
            return None, "Agent not found."

        amount = round(float(amount), 2)
        comm_ref = f"COM-MAN-{uuid.uuid4().hex[:8].upper()}"

        comm = Commission(
            commission_reference=comm_ref,
            booking_id=None,
            agent_id=agent.agent_id,
            referral_code=agent.agent_code,
            customer_id=None,
            property_id=None,
            payment_reference=f"MANUAL-{uuid.uuid4().hex[:6].upper()}",
            payment_provider='MANUAL',
            booking_amount=0.00,
            discount_percentage=0.00,
            discount_amount=0.00,
            net_booking_amount=0.00,
            commission_percentage=0.00,
            commission_amount=amount,
            currency='NGN',
            commission_status='APPROVED',
            payment_status='PENDING',
            commission_type=commission_type.upper(),
            generated_at=datetime.utcnow(),
            approved_at=datetime.utcnow(),
            approved_by=performed_by_user_id,
            notes=notes
        )
        db.session.add(comm)
        db.session.flush()

        agent.pending_commission = float(agent.pending_commission or 0) + amount

        audit = CommissionAuditLog(
            commission_id=comm.commission_id,
            action=f"MANUAL_CREATION_{commission_type}",
            old_status=None,
            new_status='APPROVED',
            performed_by=performed_by_user_id,
            remarks=f"Manual {commission_type} of ₦{amount:,.2f} recorded. Notes: {notes or 'N/A'}"
        )
        db.session.add(audit)
        db.session.commit()
        return comm, f"Manual {commission_type} of ₦{amount:,.2f} successfully created."

    @staticmethod
    def get_commission_metrics(agent_id=None):
        """
        Returns aggregate financial metrics for Commissions.
        """
        from app.models import Commission

        query = Commission.query
        if agent_id:
            query = query.filter_by(agent_id=agent_id)

        all_comms = query.all()
        total_referrals = len(all_comms)
        successful_referrals = len([c for c in all_comms if c.commission_status in ['APPROVED', 'PAID']])
        pending_comms = len([c for c in all_comms if c.commission_status == 'PENDING'])
        approved_comms = len([c for c in all_comms if c.commission_status == 'APPROVED'])
        paid_comms = len([c for c in all_comms if c.commission_status == 'PAID'])
        cancelled_comms = len([c for c in all_comms if c.commission_status in ['CANCELLED', 'REVERSED', 'FAILED']])

        total_earned = sum(float(c.commission_amount) for c in all_comms if c.commission_status in ['APPROVED', 'PAID'])
        total_paid = sum(float(c.commission_amount) for c in all_comms if c.commission_status == 'PAID')
        outstanding_balance = sum(float(c.commission_amount) for c in all_comms if c.commission_status in ['PENDING', 'APPROVED'])

        avg_booking_val = (sum(float(c.booking_amount) for c in all_comms) / total_referrals) if total_referrals > 0 else 0.0
        highest_comm = max([float(c.commission_amount) for c in all_comms], default=0.0)

        return {
            "total_referrals": total_referrals,
            "successful_referrals": successful_referrals,
            "pending_count": pending_comms,
            "approved_count": approved_comms,
            "paid_count": paid_comms,
            "cancelled_count": cancelled_comms,
            "total_earned": total_earned,
            "total_paid": total_paid,
            "outstanding_balance": outstanding_balance,
            "avg_booking_value": avg_booking_val,
            "highest_commission": highest_comm
        }

class NotificationService:
    @staticmethod
    def create_notification(recipient_id=None, notification_type=None, portal=None, title=None, message=None,
                            priority="MEDIUM", requires_action=False, related_type=None, related_id=None, action_url=None):
        """
        Centralized Notification Helper to trigger notifications across all portals.
        Includes duplicate notification prevention and automatic SuperAdmin targeting.
        """
        from app.models import Notification, User, Role
        from app.extensions import db
        from datetime import datetime, timedelta

        if not portal or not notification_type or not title or not message:
            return None, "Portal, notification_type, title, and message are required."

        priority = priority.upper() if priority else "MEDIUM"
        if priority not in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            priority = "MEDIUM"

        dedup_key = f"{portal}_{notification_type}_{related_type or ''}_{related_id or ''}"

        # Prevent duplicate active notifications within last 24 hours
        time_threshold = datetime.utcnow() - timedelta(hours=24)
        existing = Notification.query.filter(
            Notification.dedup_key == dedup_key,
            Notification.status.in_(["UNREAD", "READ", "ACTION_REQUIRED"]),
            Notification.created_at >= time_threshold
        ).first()

        if existing:
            return existing, "Duplicate notification prevented (already generated)."

        status_val = "ACTION_REQUIRED" if requires_action else "UNREAD"

        # If no recipient specified, target SuperAdmin users
        if not recipient_id:
            superadmin_role = Role.query.filter_by(role_name='SuperAdmin').first()
            superadmin_user = User.query.filter_by(role_id=superadmin_role.role_id).first() if superadmin_role else None
            recipient_id = superadmin_user.user_id if superadmin_user else None

        notification = Notification(
            recipient_id=recipient_id,
            notification_type=notification_type,
            portal=portal.upper(),
            title=title,
            message=message,
            priority=priority,
            status=status_val,
            is_read=False,
            requires_action=requires_action,
            related_id=related_id,
            related_type=related_type,
            action_url=action_url,
            dedup_key=dedup_key,
            created_at=datetime.utcnow()
        )

        db.session.add(notification)
        try:
            db.session.commit()
            return notification, "Notification created successfully."
        except Exception as e:
            db.session.rollback()
            return None, f"Failed to create notification: {str(e)}"

    @staticmethod
    def get_unread_count(user_id=None):
        from app.models import Notification
        query = Notification.query.filter_by(is_read=False)
        if user_id:
            query = query.filter((Notification.recipient_id == user_id) | (Notification.recipient_id == None))
        return query.count()

    @staticmethod
    def mark_as_read(notification_id, user_id=None):
        from app.models import Notification
        from app.extensions import db
        from datetime import datetime

        notification = Notification.query.get(notification_id)
        if not notification:
            return False, "Notification not found."

        notification.is_read = True
        if notification.status == "UNREAD":
            notification.status = "READ"
        notification.read_at = datetime.utcnow()
        db.session.commit()
        return True, "Notification marked as read."

    @staticmethod
    def mark_as_unread(notification_id, user_id=None):
        from app.models import Notification
        from app.extensions import db

        notification = Notification.query.get(notification_id)
        if not notification:
            return False, "Notification not found."

        notification.is_read = False
        if notification.status == "READ":
            notification.status = "UNREAD"
        notification.read_at = None
        db.session.commit()
        return True, "Notification marked as unread."

    @staticmethod
    def resolve_notification(notification_id, user_id=None):
        from app.models import Notification
        from app.extensions import db
        from datetime import datetime

        notification = Notification.query.get(notification_id)
        if not notification:
            return False, "Notification not found."

        notification.status = "RESOLVED"
        notification.requires_action = False
        notification.is_read = True
        notification.resolved_at = datetime.utcnow()
        db.session.commit()
        return True, "Notification resolved successfully."

class WhatsAppService:
    @staticmethod
    def send_superadmin_2fa_otp(recipient_phone, otp_code):
        import requests
        import os
        from datetime import datetime
        from flask import current_app
        from app.models import WhatsAppLog
        from app.extensions import db

        target_phone = (recipient_phone or os.environ.get('SUPERADMIN_2FA_PHONE', '+2348028331603')).strip()
        clean_recipient = target_phone.replace(' ', '').replace('-', '').replace('+', '')

        msg_text = (
            f"The Height AMRS Security Code: {otp_code}\n\n"
            "This code expires in 5 minutes and can only be used once.\n\n"
            "If you did not attempt to sign in to the Superadmin account, secure the account immediately."
        )

        api_url = current_app.config.get('WHATSAPP_API_URL') or os.environ.get('WHATSAPP_API_URL', 'https://graph.facebook.com/v18.0')
        access_token = current_app.config.get('WHATSAPP_ACCESS_TOKEN') or os.environ.get('WHATSAPP_ACCESS_TOKEN', '')
        phone_number_id = current_app.config.get('WHATSAPP_PHONE_NUMBER_ID') or os.environ.get('WHATSAPP_PHONE_NUMBER_ID', '')

        status = 'pending'
        err_msg = None

        if access_token and phone_number_id:
            try:
                endpoint = f"{api_url.rstrip('/')}/{phone_number_id}/messages"
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": clean_recipient,
                    "type": "text",
                    "text": {"preview_url": False, "body": msg_text}
                }
                resp = requests.post(endpoint, json=payload, headers=headers, timeout=10)
                if resp.status_code in [200, 201]:
                    status = 'sent'
                    current_app.logger.info(f"[2FA_WHATSAPP] OTP dispatch successful to WhatsApp ending in {clean_recipient[-4:]}")
                else:
                    status = 'failed'
                    err_msg = f"HTTP {resp.status_code}: {resp.text[:100]}"
                    current_app.logger.warning(f"[2FA_WHATSAPP] Dispatch error: {err_msg}")
            except Exception as e:
                status = 'failed'
                err_msg = str(e)
                current_app.logger.error(f"[2FA_WHATSAPP] Connection Exception: {err_msg}")
        else:
            status = 'not_configured'
            err_msg = "WhatsApp API provider credentials not configured in environment variables."
            current_app.logger.info(f"[2FA_WHATSAPP] OTP generated (WhatsApp API credentials not configured). Destination: WhatsApp ending in {clean_recipient[-4:]}")

        # Log WhatsApp entry without plaintext OTP
        try:
            log_entry = WhatsAppLog(
                recipient=clean_recipient[-4:],
                message="Superadmin 2FA Verification Code",
                status=status,
                error_message=err_msg,
                sent_at=datetime.utcnow()
            )
            db.session.add(log_entry)
            db.session.commit()
        except Exception as log_err:
            db.session.rollback()
            current_app.logger.error(f"[2FA_WHATSAPP_LOG_ERROR] {str(log_err)}")

        return (status == 'sent'), err_msg or "OTP dispatch processed."


class Superadmin2FAService:
    @staticmethod
    def generate_otp(user_id):
        import secrets
        import os
        from datetime import datetime, timedelta
        from werkzeug.security import generate_password_hash
        from flask import current_app
        from app.models import SuperadminOTP, User
        from app.extensions import db

        # Invalidate any active unused OTP for this user
        SuperadminOTP.query.filter_by(user_id=user_id, used=False).update({'used': True})
        db.session.commit()

        # Cryptographically secure 6-digit random code
        digits = '0123456789'
        otp_code = ''.join(secrets.choice(digits) for _ in range(6))
        otp_hash = generate_password_hash(otp_code)
        expires_at = datetime.utcnow() + timedelta(minutes=5)

        otp_record = SuperadminOTP(
            user_id=user_id,
            otp_hash=otp_hash,
            expires_at=expires_at,
            attempts=0,
            used=False,
            created_at=datetime.utcnow()
        )
        db.session.add(otp_record)
        db.session.commit()

        # Send via WhatsApp to registered number (+2348028331603)
        target_phone = os.environ.get('SUPERADMIN_2FA_PHONE', '+2348028331603')
        sent_ok, msg = WhatsAppService.send_superadmin_2fa_otp(target_phone, otp_code)

        current_app.logger.info(f"[2FA_SECURITY] Superadmin OTP generated for user_id={user_id}. Expiration: 5 minutes. Attempts limit: 5.")
        return otp_record, sent_ok, msg

    @staticmethod
    def verify_otp(user_id, input_otp):
        from datetime import datetime
        from werkzeug.security import check_password_hash
        from flask import current_app
        from app.models import SuperadminOTP
        from app.extensions import db

        if not input_otp or len(str(input_otp).strip()) != 6 or not str(input_otp).strip().isdigit():
            return False, "Invalid verification code format. Enter a 6-digit code."

        input_otp = str(input_otp).strip()

        otp_record = SuperadminOTP.query.filter_by(user_id=user_id, used=False).order_by(SuperadminOTP.created_at.desc()).first()

        if not otp_record:
            current_app.logger.warning(f"[2FA_SECURITY] OTP verification failed: No active code for user_id={user_id}.")
            return False, "No active verification code found. Please request a new code."

        if datetime.utcnow() > otp_record.expires_at:
            otp_record.used = True
            db.session.commit()
            current_app.logger.warning(f"[2FA_SECURITY] OTP verification failed: Expired code for user_id={user_id}.")
            return False, "Verification code has expired. Please request a new code."

        if otp_record.attempts >= 5:
            otp_record.used = True
            db.session.commit()
            current_app.logger.warning(f"[2FA_SECURITY] OTP verification failed: Maximum attempts exceeded for user_id={user_id}.")
            return False, "Maximum verification attempts exceeded. Code invalidated. Please request a new code."

        otp_record.attempts += 1

        if check_password_hash(otp_record.otp_hash, input_otp):
            otp_record.used = True
            otp_record.used_at = datetime.utcnow()
            db.session.commit()
            current_app.logger.info(f"[2FA_SECURITY] Superadmin 2FA verification SUCCESS for user_id={user_id}.")
            return True, "Two-Factor Verification Successful."
        else:
            db.session.commit()
            current_app.logger.warning(f"[2FA_SECURITY] OTP verification failed: Incorrect code attempt #{otp_record.attempts} for user_id={user_id}.")
            return False, "Invalid verification code."


