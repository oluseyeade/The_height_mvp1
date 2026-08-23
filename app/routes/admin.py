from flask import render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_user, current_user
from app.decorators import admin_only
from app.models import User
from app.extensions import db
from app.services import ApartmentService

apt_service = ApartmentService()

from datetime import datetime
from flask import session
from app.services import Superadmin2FAService

def init_admin_routes(app):
    @app.route('/admin/login', methods=['GET', 'POST'], endpoint='admin_panel.admin_login')
    def admin_login():
        if current_user.is_authenticated:
            if current_user.is_superadmin:
                return redirect(url_for('superadmin_panel.dashboard'))
            elif current_user.is_admin:
                return redirect(url_for('admin_panel.dashboard'))

        if request.method == 'POST':
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')

            user = User.query.filter_by(email=email).first()

            if user and user.check_password(password):
                if user.is_superadmin:
                    # Mandatory 2FA Flow for Superadmin
                    session['2fa_pending_user_id'] = user.user_id
                    session['2fa_pending_time'] = datetime.utcnow().timestamp()
                    _, sent_ok, msg = Superadmin2FAService.generate_otp(user.user_id)

                    flash('Credentials verified. Two-Factor Authentication code sent to registered WhatsApp ending in 1603.', 'info')
                    return redirect(url_for('admin_panel.superadmin_2fa'))
                elif user.is_admin:
                    login_user(user)
                    flash(f'Welcome, {user.full_name}! Admin session initiated.', 'success')
                    return redirect(url_for('admin_panel.dashboard'))
                else:
                    flash('Invalid administrative credentials or insufficient privileges.', 'danger')
            else:
                flash('Invalid administrative credentials or insufficient privileges.', 'danger')

        return render_template('admin_panel/admin_login.html')

    @app.route('/admin/superadmin/2fa', methods=['GET'], endpoint='admin_panel.superadmin_2fa')
    def superadmin_2fa():
        pending_user_id = session.get('2fa_pending_user_id')
        pending_time = session.get('2fa_pending_time')

        if not pending_user_id or not pending_time or (datetime.utcnow().timestamp() - pending_time > 600):
            session.pop('2fa_pending_user_id', None)
            session.pop('2fa_pending_time', None)
            flash('2FA session expired. Please log in again.', 'warning')
            return redirect(url_for('admin_panel.admin_login'))

        return render_template('admin_panel/superadmin_2fa.html')

    @app.route('/admin/superadmin/2fa/verify', methods=['POST'], endpoint='admin_panel.superadmin_2fa_verify')
    def superadmin_2fa_verify():
        pending_user_id = session.get('2fa_pending_user_id')

        if not pending_user_id:
            flash('No pending 2FA authentication session. Please log in.', 'warning')
            return redirect(url_for('admin_panel.admin_login'))

        otp_code = request.form.get('otp_code', '').strip()

        ok, msg = Superadmin2FAService.verify_otp(pending_user_id, otp_code)

        if ok:
            user = User.query.get(pending_user_id)
            if not user or not user.is_superadmin:
                session.pop('2fa_pending_user_id', None)
                flash('Insufficient privileges for SuperAdmin access.', 'danger')
                return redirect(url_for('admin_panel.admin_login'))

            session.pop('2fa_pending_user_id', None)
            session.pop('2fa_pending_time', None)
            login_user(user)
            flash(f'Welcome, {user.full_name}! SuperAdmin 2FA session authenticated successfully.', 'success')
            return redirect(url_for('superadmin_panel.dashboard'))
        else:
            flash(msg, 'danger')
            return redirect(url_for('admin_panel.superadmin_2fa'))

    @app.route('/admin/superadmin/2fa/resend', methods=['POST'], endpoint='admin_panel.superadmin_2fa_resend')
    def superadmin_2fa_resend():
        pending_user_id = session.get('2fa_pending_user_id')

        if not pending_user_id:
            flash('No pending 2FA authentication session. Please log in.', 'warning')
            return redirect(url_for('admin_panel.admin_login'))

        last_resend = session.get('last_otp_resend', 0)
        now_ts = datetime.utcnow().timestamp()

        if now_ts - last_resend < 60:
            cooldown_rem = int(60 - (now_ts - last_resend))
            flash(f'Please wait {cooldown_rem} seconds before requesting a new verification code.', 'warning')
            return redirect(url_for('admin_panel.superadmin_2fa'))

        session['last_otp_resend'] = now_ts
        _, sent_ok, msg = Superadmin2FAService.generate_otp(pending_user_id)

        flash('A new 2FA verification code has been sent to WhatsApp ending in 1603.', 'success')
        return redirect(url_for('admin_panel.superadmin_2fa'))


    @app.route('/admin/', endpoint='admin_panel.dashboard')
    @admin_only
    def admin_dashboard_route():
        apartments = apt_service.get_all_active_apartments()
        return render_template('dashboard/admin_dashboard.html', apartments=apartments)

    @app.route('/admin/apartments/<int:apartment_id>/price', methods=['POST'], endpoint='admin_panel.update_apartment_price')
    @admin_only
    def update_price_route(apartment_id):
        new_price = request.form.get('price_per_night')
        apt, msg = apt_service.update_apartment_price(apartment_id, new_price)
        if apt:
            flash(msg, 'success')
        else:
            flash(msg, 'danger')
        return redirect(url_for('admin_panel.dashboard'))

    # -------------------------------------------------------------------------
    # ENTERPRISE COMMISSION MANAGEMENT ROUTES
    # -------------------------------------------------------------------------
    @app.route('/admin/commissions', methods=['GET'], endpoint='admin_panel.manage_commissions')
    @admin_only
    def manage_commissions():
        from app.models import Commission, CommissionAuditLog, Agent
        from app.services import CommissionService

        status_filter = request.args.get('status', '').strip().upper()
        search_query = request.args.get('search', '').strip()

        query = Commission.query
        if status_filter:
            query = query.filter_by(commission_status=status_filter)
        if search_query:
            query = query.filter(
                (Commission.commission_reference.like(f"%{search_query}%")) |
                (Commission.referral_code.like(f"%{search_query}%")) |
                (Commission.payment_reference.like(f"%{search_query}%"))
            )

        commissions = query.order_by(Commission.created_at.desc()).all()
        metrics = CommissionService.get_commission_metrics()
        agents = Agent.query.filter_by(status='active').all()

        return render_template(
            'admin/manage_commissions.html',
            commissions=commissions,
            metrics=metrics,
            agents=agents,
            status_filter=status_filter,
            search_query=search_query
        )

    @app.route('/admin/commissions/<int:commission_id>/status', methods=['POST'], endpoint='admin_panel.update_commission_status')
    @admin_only
    def update_commission_status_route(commission_id):
        from app.services import CommissionService

        new_status = request.form.get('status', '').strip().upper()
        remarks = request.form.get('remarks', '').strip()
        ip_addr = request.remote_addr
        user_agent = request.user_agent.string[:250] if request.user_agent else ''

        succ, msg = CommissionService.update_commission_status(
            commission_id=commission_id,
            new_status=new_status,
            performed_by_user_id=current_user.user_id,
            remarks=remarks,
            ip_address=ip_addr,
            device=user_agent
        )

        if succ:
            flash(msg, 'success')
        else:
            flash(msg, 'danger')
        return redirect(request.referrer or url_for('admin_panel.dashboard'))

    @app.route('/admin/commissions/manual', methods=['POST'], endpoint='admin_panel.create_manual_commission')
    @admin_only
    def create_manual_commission_route():
        from app.services import CommissionService

        agent_id = request.form.get('agent_id')
        amount = request.form.get('amount')
        comm_type = request.form.get('commission_type', 'BONUS')
        notes = request.form.get('notes', '').strip()

        comm, msg = CommissionService.create_manual_commission(
            agent_id=agent_id,
            amount=amount,
            commission_type=comm_type,
            notes=notes,
            performed_by_user_id=current_user.user_id
        )

        if comm:
            flash(msg, 'success')
        else:
            flash(msg, 'danger')
        return redirect(request.referrer or url_for('admin_panel.dashboard'))

    @app.route('/admin/commissions/export', methods=['GET'], endpoint='admin_panel.export_commissions')
    @admin_only
    def export_commissions_route():
        import csv, io
        from flask import Response
        from app.models import Commission

        commissions = Commission.query.order_by(Commission.created_at.desc()).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'Commission Ref', 'Booking ID', 'Agent Code', 'Payment Ref',
            'Booking Amount (NGN)', 'Discount (NGN)', 'Net Amount (NGN)',
            'Commission Rate (%)', 'Commission Amount (NGN)', 'Status',
            'Payment Provider', 'Generated At', 'Paid At'
        ])

        for c in commissions:
            writer.writerow([
                c.commission_reference, c.booking_id or 'N/A', c.referral_code,
                c.payment_reference, f"{float(c.booking_amount):.2f}",
                f"{float(c.discount_amount):.2f}", f"{float(c.net_booking_amount):.2f}",
                f"{float(c.commission_percentage):.2f}", f"{float(c.commission_amount):.2f}",
                c.commission_status, c.payment_provider,
                c.generated_at.strftime('%Y-%m-%d %H:%M:%S') if c.generated_at else '',
                c.paid_at.strftime('%Y-%m-%d %H:%M:%S') if c.paid_at else ''
            ])

        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment;filename=commission_report.csv'}
        )

    # -------------------------------------------------------------------------
    # ENTERPRISE BOOKINGS MANAGEMENT MODULE
    # -------------------------------------------------------------------------
    @app.route('/admin/bookings', methods=['GET'], endpoint='admin_panel.manage_bookings')
    @admin_only
    def manage_bookings():
        from datetime import datetime, timedelta
        from sqlalchemy import or_
        from app.models import Booking, Apartment, Payment, Receipt, Agent

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        status_filter = request.args.get('status', '').strip().lower()
        payment_status_filter = request.args.get('payment_status', '').strip().upper()
        apartment_id_filter = request.args.get('apartment_id', type=int)
        search_query = request.args.get('search', '').strip()
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()

        query = Booking.query

        if status_filter and status_filter != 'all':
            query = query.filter(Booking.status.ilike(status_filter))

        if payment_status_filter and payment_status_filter != 'ALL':
            query = query.filter(Booking.payment_status == payment_status_filter)

        if apartment_id_filter:
            query = query.filter_by(apartment_id=apartment_id_filter)

        if search_query:
            query = query.filter(
                or_(
                    Booking.booking_ref.ilike(f"%{search_query}%"),
                    Booking.guest_name.ilike(f"%{search_query}%"),
                    Booking.guest_email.ilike(f"%{search_query}%"),
                    Booking.guest_phone.ilike(f"%{search_query}%"),
                    Booking.payment_reference.ilike(f"%{search_query}%")
                )
            )

        if start_date:
            try:
                s_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(Booking.check_in >= s_dt)
            except ValueError:
                pass

        if end_date:
            try:
                e_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(Booking.check_in <= e_dt)
            except ValueError:
                pass

        pagination = query.order_by(Booking.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        bookings = pagination.items

        # Real-time Metrics Calculation
        all_b_query = Booking.query.all()
        total_bookings_count = len(all_b_query)
        confirmed_count = len([b for b in all_b_query if b.status in ['confirmed', 'CONFIRMED', 'checked_in', 'CHECKED_IN']])
        checked_in_count = len([b for b in all_b_query if b.status in ['checked_in', 'CHECKED_IN']])
        total_room_revenue = sum(float(b.final_amount or b.total_price) for b in all_b_query if b.status in ['confirmed', 'CONFIRMED', 'checked_in', 'CHECKED_IN', 'checked_out', 'CHECKED_OUT'])
        total_caution_held = sum(float(b.caution_fee or 50000.00) for b in all_b_query if b.status in ['confirmed', 'CONFIRMED', 'checked_in', 'CHECKED_IN'])

        metrics = {
            'total_bookings': total_bookings_count,
            'confirmed_count': confirmed_count,
            'checked_in_count': checked_in_count,
            'total_room_revenue': total_room_revenue,
            'total_caution_held': total_caution_held
        }

        apartments = Apartment.query.all()

        return render_template(
            'admin/manage_bookings.html',
            bookings=bookings,
            pagination=pagination,
            metrics=metrics,
            apartments=apartments,
            status_filter=status_filter,
            payment_status_filter=payment_status_filter,
            apartment_id_filter=apartment_id_filter,
            search_query=search_query,
            start_date=start_date,
            end_date=end_date
        )

    # -------------------------------------------------------------------------
    # MANAGEMENT RESERVATIONS & CALENDAR AVAILABILITY API ENDPOINTS
    # -------------------------------------------------------------------------
    @app.route('/admin/api/apartments/<int:apartment_id>/calendar-availability', methods=['GET'], endpoint='admin_panel.api_calendar_availability')
    @admin_only
    def api_calendar_availability(apartment_id):
        from datetime import date, timedelta
        from app.models import Apartment, Booking, Availability

        apt = Apartment.query.get_or_404(apartment_id)
        today = date.today()
        calendar_data = []

        for i in range(30):
            curr_date = today + timedelta(days=i)
            
            # Check if date is booked by active reservation
            booked = Booking.query.filter(
                Booking.apartment_id == apartment_id,
                Booking.status.in_(['confirmed', 'CONFIRMED', 'active', 'ACTIVE', 'checked_in', 'CHECKED_IN']),
                Booking.check_in <= curr_date,
                Booking.check_out > curr_date
            ).first()

            # Check if date is blocked on Availability table
            blocked = Availability.query.filter_by(
                apartment_id=apartment_id,
                date=curr_date,
                status='blocked'
            ).first()

            if booked or blocked:
                st = 'booked' if booked else 'blocked'
                icon = '🔴 Booked' if booked else '🔴 Blocked'
            else:
                st = 'available'
                icon = '🟢 Available'

            calendar_data.append({
                'date': curr_date.strftime('%Y-%m-%d'),
                'day_label': curr_date.strftime('%b %d'),
                'status': st,
                'status_icon': icon
            })

        return jsonify({
            'apartment_id': apartment_id,
            'apartment_title': apt.title,
            'calendar': calendar_data
        })

    @app.route('/admin/bookings/management-reservation', methods=['POST'], endpoint='admin_panel.create_management_reservation')
    @admin_only
    def create_management_reservation_route():
        from datetime import datetime, date, timedelta
        from app.models import Apartment, Booking, Availability, AuditLog
        from app.services import BookingService, NotificationService

        apt_id = request.form.get('apartment_id', type=int)
        booking_type = request.form.get('booking_type', 'regular').strip().lower()
        company_name = request.form.get('company_name', '').strip()
        guest_name = request.form.get('guest_name', '').strip()
        guest_email = request.form.get('guest_email', '').strip()
        guest_phone = request.form.get('guest_phone', '').strip()
        guest_count = request.form.get('guest_count', 1, type=int)
        check_in_str = request.form.get('check_in', '').strip()
        check_out_str = request.form.get('check_out', '').strip()
        special_requests = request.form.get('special_requests', '').strip()

        try:
            check_in_dt = datetime.strptime(check_in_str, '%Y-%m-%d').date()
            check_out_dt = datetime.strptime(check_out_str, '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid check-in or check-out date format.", "danger")
            return redirect(request.referrer or url_for('admin_panel.manage_bookings'))

        if check_in_dt >= check_out_dt:
            flash("Check-out date must be after check-in date.", "danger")
            return redirect(request.referrer or url_for('admin_panel.manage_bookings'))

        # FINAL SERVER-SIDE AVAILABILITY CHECK
        overlap = Booking.query.filter(
            Booking.apartment_id == apt_id,
            Booking.status.in_(['confirmed', 'CONFIRMED', 'active', 'ACTIVE', 'checked_in', 'CHECKED_IN']),
            Booking.check_in < check_out_dt,
            Booking.check_out > check_in_dt
        ).first()

        if overlap:
            flash("Selected dates overlap with an existing reservation. Please choose different dates.", "danger")
            return redirect(request.referrer or url_for('admin_panel.manage_bookings'))

        overlap_block = Availability.query.filter(
            Availability.apartment_id == apt_id,
            Availability.status == 'blocked',
            Availability.date >= check_in_dt,
            Availability.date < check_out_dt
        ).first()

        if overlap_block:
            flash("Selected date range contains a management-blocked period. Please select different dates.", "danger")
            return redirect(request.referrer or url_for('admin_panel.manage_bookings'))

        # Construct full guest name / notes if Corporate Customer
        full_name = f"{company_name} / {guest_name}" if (booking_type == 'corporate' and company_name) else guest_name
        notes = f"[Corporate Reservation: {company_name}] {special_requests}" if (booking_type == 'corporate' and company_name) else special_requests

        b_service = BookingService()
        booking, msg = b_service.create_booking(
            apartment_id=apt_id,
            check_in_date=check_in_dt,
            check_out_date=check_out_dt,
            guest_name=full_name,
            guest_email=guest_email,
            guest_phone=guest_phone,
            guest_count=guest_count,
            special_requests=notes,
            source='management_corporate' if booking_type == 'corporate' else 'management'
        )

        if not booking:
            flash(f"Reservation creation failed: {msg}", "danger")
            return redirect(request.referrer or url_for('admin_panel.manage_bookings'))

        # Immediately Confirm Management Reservation
        booking.status = 'confirmed'
        booking.booking_status = 'Confirmed'
        booking.payment_status = 'VERIFIED'

        # Block dates on Availability table
        curr = check_in_dt
        while curr < check_out_dt:
            avail = Availability.query.filter_by(apartment_id=apt_id, date=curr).first()
            if not avail:
                avail = Availability(apartment_id=apt_id, date=curr, status='booked')
                db.session.add(avail)
            else:
                avail.status = 'booked'
            curr += timedelta(days=1)

        db.session.commit()

        # Audit & SuperAdmin Notification
        audit = AuditLog(
            user_id=current_user.user_id,
            action='CREATE_MANAGEMENT_RESERVATION',
            activity_type='MANAGEMENT_RESERVATION',
            module='RESERVATIONS',
            ip_address=request.remote_addr,
            description=f"Created {booking_type.upper()} reservation ({booking.booking_ref}) for {full_name} ({check_in_str} to {check_out_str})"
        )
        db.session.add(audit)
        db.session.commit()

        NotificationService.create_notification(
            title=f"Management Reservation Created ({booking.booking_ref})",
            message=f"Admin {current_user.full_name} created a {booking_type.upper()} reservation for {full_name}.",
            notification_type='BOOKING',
            related_type='BOOKING',
            related_id=str(booking.booking_ref)
        )

        flash(f"Management Reservation ({booking.booking_ref}) created and confirmed successfully for {full_name}!", "success")
        return redirect(url_for('admin_panel.manage_bookings'))

    @app.route('/admin/bookings/block-dates', methods=['POST'], endpoint='admin_panel.block_property_dates')
    @admin_only
    def block_property_dates_route():
        from datetime import datetime, date, timedelta
        from app.models import Availability, AuditLog

        apt_id = request.form.get('apartment_id', type=int)
        check_in_str = request.form.get('check_in', '').strip()
        check_out_str = request.form.get('check_out', '').strip()
        reason = request.form.get('reason', 'Management Block').strip()

        try:
            check_in_dt = datetime.strptime(check_in_str, '%Y-%m-%d').date()
            check_out_dt = datetime.strptime(check_out_str, '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid check-in or check-out date format.", "danger")
            return redirect(request.referrer or url_for('admin_panel.manage_bookings'))

        if check_in_dt >= check_out_dt:
            flash("Check-out date must be after check-in date.", "danger")
            return redirect(request.referrer or url_for('admin_panel.manage_bookings'))

        curr = check_in_dt
        count = 0
        while curr < check_out_dt:
            avail = Availability.query.filter_by(apartment_id=apt_id, date=curr).first()
            if not avail:
                avail = Availability(apartment_id=apt_id, date=curr, status='blocked')
                db.session.add(avail)
            else:
                avail.status = 'blocked'
            curr += timedelta(days=1)
            count += 1

        db.session.commit()

        audit = AuditLog(
            user_id=current_user.user_id,
            action='BLOCK_PROPERTY_DATES',
            activity_type='DATE_BLOCKING',
            module='AVAILABILITY',
            ip_address=request.remote_addr,
            description=f"Blocked {count} date(s) for Apartment #{apt_id} ({check_in_str} to {check_out_str}). Reason: {reason}"
        )
        db.session.add(audit)
        db.session.commit()

        flash(f"Successfully blocked {count} night(s) for Apartment #{apt_id}!", "success")
        return redirect(url_for('admin_panel.manage_bookings'))

    @app.route('/admin/bookings/<int:booking_id>/status', methods=['POST'], endpoint='admin_panel.update_booking_status')
    @admin_only
    def update_booking_status_route(booking_id):
        from datetime import datetime, timedelta
        from app.models import Booking, Availability
        from app.extensions import db

        booking = Booking.query.get(booking_id)
        if not booking:
            flash('Booking record not found.', 'danger')
            return redirect(url_for('admin_panel.manage_bookings'))

        new_status = request.form.get('status', '').strip().lower()
        if new_status not in ['confirmed', 'checked_in', 'checked_out', 'cancelled', 'pending']:
            flash('Invalid booking status provided.', 'danger')
            return redirect(url_for('admin_panel.manage_bookings'))

        old_status = booking.status
        booking.status = new_status
        booking.booking_status = new_status.replace('_', ' ').title()

        if new_status in ['confirmed', 'checked_in']:
            booking.payment_status = 'VERIFIED'
            if new_status == 'checked_in':
                booking.checked_in_at = datetime.utcnow()
            elif new_status == 'confirmed':
                booking.verified_at = datetime.utcnow()

            # Ensure calendar dates are blocked
            curr_d = booking.check_in
            while curr_d < booking.check_out:
                avail = Availability.query.filter_by(apartment_id=booking.apartment_id, date=curr_d).first()
                if not avail:
                    db.session.add(Availability(apartment_id=booking.apartment_id, date=curr_d, status='booked'))
                else:
                    avail.status = 'booked'
                curr_d += timedelta(days=1)

        elif new_status == 'checked_out':
            booking.checked_out_at = datetime.utcnow()

        elif new_status == 'cancelled':
            booking.payment_status = 'CANCELLED'
            # Release blocked dates
            Availability.query.filter_by(apartment_id=booking.apartment_id).filter(
                Availability.date >= booking.check_in,
                Availability.date < booking.check_out
            ).delete()

        db.session.commit()
        flash(f"Booking {booking.booking_ref} status updated from '{old_status}' to '{new_status}' successfully.", 'success')
        return redirect(url_for('admin_panel.manage_bookings'))

    @app.route('/admin/bookings/export', methods=['GET'], endpoint='admin_panel.export_bookings')
    @admin_only
    def export_bookings():
        import csv
        import io
        from flask import Response
        from app.models import Booking

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'Booking Reference', 'Customer Name', 'Customer Email', 'Customer Phone',
            'Apartment Title', 'Check-in Date', 'Check-out Date', 'Nights',
            'Room Fee (NGN)', 'Discount (NGN)', 'Caution Fee (NGN)', 'Total Amount (NGN)',
            'Payment Status', 'Paystack Reference', 'Booking Status', 'Referral Code', 'Created Date'
        ])

        bookings = Booking.query.order_by(Booking.created_at.desc()).all()
        for b in bookings:
            num_nights = (b.check_out - b.check_in).days if b.check_in and b.check_out else 1
            apt_title = b.apartment.title if b.apartment else 'N/A'
            ref_code = b.agent.agent_code if b.agent else 'None'
            writer.writerow([
                b.booking_ref, b.guest_name or 'N/A', b.guest_email or 'N/A', b.guest_phone or 'N/A',
                apt_title, b.check_in, b.check_out, num_nights,
                b.total_price or b.final_amount, b.discount_amount, b.caution_fee, b.total_amount,
                b.payment_status, b.payment_reference or 'N/A', b.status, ref_code, b.created_at
            ])

        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=bookings_report.csv'}
        )

    # -------------------------------------------------------------------------
    # ENTERPRISE CORPORATE BOOKING REQUEST MANAGEMENT MODULE
    # -------------------------------------------------------------------------
    @app.route('/admin/corporate', methods=['GET'], endpoint='admin_panel.manage_corporate')
    @admin_only
    def manage_corporate():
        from datetime import datetime
        from sqlalchemy import or_
        from app.models import CorporateEnquiry, CorporateQuote, CorporateAuditLog, User, Apartment

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        status_filter = request.args.get('status', '').strip().lower()
        search_query = request.args.get('search', '').strip()
        assigned_filter = request.args.get('assigned_to', type=int)

        query = CorporateEnquiry.query

        # RBAC: Standard Admins see assigned/unassigned requests, SuperAdmin sees all
        if not current_user.is_superadmin:
            query = query.filter(
                or_(
                    CorporateEnquiry.assigned_to == current_user.user_id,
                    CorporateEnquiry.assigned_to.is_(None)
                )
            )

        if status_filter and status_filter != 'all':
            query = query.filter(CorporateEnquiry.status.ilike(status_filter))

        if assigned_filter:
            query = query.filter_by(assigned_to=assigned_filter)

        if search_query:
            query = query.filter(
                or_(
                    CorporateEnquiry.company_name.ilike(f"%{search_query}%"),
                    CorporateEnquiry.contact_person.ilike(f"%{search_query}%"),
                    CorporateEnquiry.email.ilike(f"%{search_query}%"),
                    CorporateEnquiry.phone.ilike(f"%{search_query}%")
                )
            )

        pagination = query.order_by(CorporateEnquiry.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        enquiries = pagination.items

        # Real-time Metrics Calculation
        all_enquiries = CorporateEnquiry.query.all()
        metrics = {
            'total_requests': len(all_enquiries),
            'new_requests': len([e for e in all_enquiries if e.status == 'new']),
            'under_review': len([e for e in all_enquiries if e.status in ['under_review', 'quotation_sent']]),
            'awaiting_payment': len([e for e in all_enquiries if e.status == 'awaiting_payment']),
            'completed': len([e for e in all_enquiries if e.status in ['confirmed', 'checked_in', 'checked_out', 'completed']]),
            'total_revenue': sum(float(e.quoted_amount or 0.00) for e in all_enquiries if e.status in ['confirmed', 'checked_in', 'checked_out', 'completed'])
        }

        from app.models import Role
        admins = User.query.join(User.role).filter(Role.role_name.in_(['Admin', 'SuperAdmin'])).all()
        if not admins:
            admins = User.query.all()

        apartments = Apartment.query.all()

        return render_template(
            'admin/manage_corporate.html',
            enquiries=enquiries,
            pagination=pagination,
            metrics=metrics,
            admins=admins,
            apartments=apartments,
            status_filter=status_filter,
            search_query=search_query,
            assigned_filter=assigned_filter
        )

    @app.route('/admin/corporate/<int:enquiry_id>/status', methods=['POST'], endpoint='admin_panel.update_corporate_status')
    @admin_only
    def update_corporate_status_route(enquiry_id):
        from datetime import datetime
        from app.models import CorporateEnquiry, CorporateAuditLog
        from app.extensions import db

        enquiry = CorporateEnquiry.query.get(enquiry_id)
        if not enquiry:
            flash('Corporate request record not found.', 'danger')
            return redirect(url_for('admin_panel.manage_corporate'))

        new_status = request.form.get('status', '').strip().lower()
        remarks = request.form.get('remarks', '').strip()
        ip_addr = request.remote_addr

        old_status = enquiry.status
        enquiry.status = new_status

        if new_status == 'approved':
            enquiry.approved_by = current_user.user_id
        elif new_status == 'rejected':
            enquiry.rejected_by = current_user.user_id
            enquiry.rejection_reason = remarks

        audit = CorporateAuditLog(
            enquiry_id=enquiry_id,
            action=f"STATUS_CHANGE_{new_status.upper()}",
            old_status=old_status,
            new_status=new_status,
            performed_by=current_user.user_id,
            ip_address=ip_addr,
            remarks=remarks or f"Status updated to '{new_status}'"
        )
        db.session.add(audit)
        db.session.commit()

        flash(f"Corporate request #{enquiry_id} for '{enquiry.company_name}' updated to '{new_status}' successfully.", 'success')
        return redirect(url_for('admin_panel.manage_corporate'))

    @app.route('/admin/corporate/<int:enquiry_id>/assign', methods=['POST'], endpoint='admin_panel.assign_corporate')
    @admin_only
    def assign_corporate_route(enquiry_id):
        from app.models import CorporateEnquiry, CorporateAuditLog, User
        from app.extensions import db

        enquiry = CorporateEnquiry.query.get(enquiry_id)
        if not enquiry:
            flash('Corporate request not found.', 'danger')
            return redirect(url_for('admin_panel.manage_corporate'))

        admin_id = request.form.get('admin_id', type=int)
        assignee = User.query.get(admin_id) if admin_id else None

        enquiry.assigned_to = admin_id
        if enquiry.status == 'new':
            enquiry.status = 'under_review'

        audit = CorporateAuditLog(
            enquiry_id=enquiry_id,
            action='ASSIGN_ADMIN',
            old_status=enquiry.status,
            new_status=enquiry.status,
            performed_by=current_user.user_id,
            ip_address=request.remote_addr,
            remarks=f"Assigned to {assignee.full_name if assignee else 'Unassigned'}"
        )
        db.session.add(audit)
        db.session.commit()

        flash(f"Corporate request #{enquiry_id} assigned to '{assignee.full_name if assignee else 'Unassigned'}' successfully.", 'success')
        return redirect(url_for('admin_panel.manage_corporate'))

    @app.route('/admin/corporate/<int:enquiry_id>/quote', methods=['POST'], endpoint='admin_panel.send_corporate_quote')
    @admin_only
    def send_corporate_quote_route(enquiry_id):
        import uuid
        from datetime import datetime, timedelta
        from app.models import CorporateEnquiry, CorporateQuote, CorporateAuditLog
        from app.extensions import db

        enquiry = CorporateEnquiry.query.get(enquiry_id)
        if not enquiry:
            flash('Corporate request not found.', 'danger')
            return redirect(url_for('admin_panel.manage_corporate'))

        try:
            amount = float(request.form.get('amount', 0))
            discount = float(request.form.get('discount', 0))
            final_amount = max(0.0, amount - discount)
            room_type = request.form.get('room_type', 'Executive Suite')
            terms = request.form.get('terms', 'Payment due prior to check-in')
            valid_days = int(request.form.get('valid_days', 7))

            valid_until = datetime.utcnow().date() + timedelta(days=valid_days)

            quote = CorporateQuote(
                enquiry_id=enquiry_id,
                created_by=current_user.user_id,
                quote_number=f"QT-THA-{uuid.uuid4().hex[:6].upper()}",
                amount=amount,
                discount=discount,
                final_amount=final_amount,
                room_type=room_type,
                terms=terms,
                valid_until=valid_until,
                status='sent',
                sent_at=datetime.utcnow()
            )
            db.session.add(quote)

            enquiry.quoted_amount = final_amount
            enquiry.total_amount = round(final_amount + float(enquiry.caution_fee or 50000.00), 2)
            enquiry.status = 'quotation_sent'

            audit = CorporateAuditLog(
                enquiry_id=enquiry_id,
                action='SEND_QUOTATION',
                old_status=enquiry.status,
                new_status='quotation_sent',
                performed_by=current_user.user_id,
                ip_address=request.remote_addr,
                remarks=f"Quotation {quote.quote_number} generated for NGN {final_amount:,.2f}"
            )
            db.session.add(audit)
            db.session.commit()

            flash(f"Quotation {quote.quote_number} sent to '{enquiry.company_name}' successfully!", 'success')
        except Exception as e:
            db.session.rollback()
            flash(f"Error generating quotation: {str(e)}", 'danger')

        return redirect(url_for('admin_panel.manage_corporate'))

    @app.route('/admin/corporate/<int:enquiry_id>/convert', methods=['POST'], endpoint='admin_panel.convert_corporate_booking')
    @admin_only
    def convert_corporate_booking_route(enquiry_id):
        import uuid
        from datetime import datetime, timedelta
        from app.models import CorporateEnquiry, Booking, Payment, Receipt, Availability, Apartment, CorporateAuditLog
        from app.extensions import db

        enquiry = CorporateEnquiry.query.get(enquiry_id)
        if not enquiry:
            flash('Corporate enquiry not found.', 'danger')
            return redirect(url_for('admin_panel.manage_corporate'))

        apt_id = request.form.get('apartment_id', type=int) or enquiry.apartment_id
        if not apt_id:
            apt = Apartment.query.filter_by(status='available').first()
            apt_id = apt.apartment_id if apt else 5

        payment_ref = request.form.get('payment_reference') or f"PAY-CORP-{uuid.uuid4().hex[:8].upper()}"

        num_nights = (enquiry.check_out - enquiry.check_in).days if enquiry.check_in and enquiry.check_out else 1
        room_fee = float(enquiry.quoted_amount or 150000.00)
        caution = float(enquiry.caution_fee or 50000.00)
        total_online = round(room_fee + caution, 2)

        # Create Confirmed Booking Record
        booking = Booking(
            apartment_id=apt_id,
            check_in=enquiry.check_in,
            check_out=enquiry.check_out,
            guest_count=enquiry.guest_count,
            total_price=room_fee,
            discount_amount=0.00,
            final_amount=room_fee,
            caution_fee_amount=caution,
            caution_fee=caution,
            total_amount=total_online,
            payment_status='VERIFIED',
            booking_status='Confirmed',
            booking_ref=f"THA-CORP-{uuid.uuid4().hex[:6].upper()}",
            status='confirmed',
            payment_reference=payment_ref,
            guest_name=f"{enquiry.company_name} ({enquiry.contact_person})",
            guest_email=enquiry.email,
            guest_phone=enquiry.phone,
            special_requests=enquiry.special_requests,
            source='corporate'
        )
        db.session.add(booking)
        db.session.flush()

        # Create Verified Payment Record
        payment = Payment(
            booking_id=booking.booking_id,
            amount=total_online,
            payment_method='corporate_bank_transfer',
            transaction_ref=payment_ref,
            paystack_reference=payment_ref,
            status='verified',
            verification_status='verified',
            verified_at=datetime.utcnow()
        )
        db.session.add(payment)
        db.session.flush()

        # Create Branded Receipt Record
        receipt = Receipt(
            payment_id=payment.payment_id,
            receipt_number=f"RCP-CORP-{uuid.uuid4().hex[:6].upper()}",
            generated_at=datetime.utcnow()
        )
        db.session.add(receipt)

        # Block Availability Calendar
        curr_d = enquiry.check_in
        while curr_d < enquiry.check_out:
            avail = Availability.query.filter_by(apartment_id=apt_id, date=curr_d).first()
            if not avail:
                db.session.add(Availability(apartment_id=apt_id, date=curr_d, status='booked'))
            else:
                avail.status = 'booked'
            curr_d += timedelta(days=1)

        # Update Corporate Enquiry Record
        enquiry.booking_id = booking.booking_id
        enquiry.apartment_id = apt_id
        enquiry.payment_status = 'VERIFIED'
        enquiry.payment_reference = payment_ref
        enquiry.status = 'confirmed'

        audit = CorporateAuditLog(
            enquiry_id=enquiry_id,
            action='CONVERT_TO_BOOKING',
            old_status='awaiting_payment',
            new_status='confirmed',
            performed_by=current_user.user_id,
            ip_address=request.remote_addr,
            remarks=f"Converted to Confirmed Booking {booking.booking_ref} & Receipt {receipt.receipt_number}"
        )
        db.session.add(audit)
        db.session.commit()

        flash(f"Corporate request #{enquiry_id} converted to Confirmed Reservation {booking.booking_ref} successfully!", 'success')
        return redirect(url_for('admin_panel.manage_corporate'))

    @app.route('/admin/corporate/export', methods=['GET'], endpoint='admin_panel.export_corporate')
    @admin_only
    def export_corporate_route():
        import csv
        import io
        from flask import Response
        from app.models import CorporateEnquiry

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'Request ID', 'Company Name', 'Contact Person', 'Email', 'Phone',
            'Check-in Date', 'Check-out Date', 'Nights', 'Guest Count', 'Suite Count',
            'Quoted Amount (NGN)', 'Caution Fee (NGN)', 'Total Amount (NGN)',
            'Status', 'Payment Status', 'Assigned Admin', 'Submitted Date'
        ])

        enquiries = CorporateEnquiry.query.order_by(CorporateEnquiry.created_at.desc()).all()
        for e in enquiries:
            num_nights = (e.check_out - e.check_in).days if e.check_in and e.check_out else 1
            assigned_name = e.assigned_admin.full_name if e.assigned_admin else 'Unassigned'
            writer.writerow([
                f"CORP-{e.enquiry_id}", e.company_name, e.contact_person, e.email, e.phone,
                e.check_in, e.check_out, num_nights, e.guest_count, e.suite_count,
                f"{float(e.quoted_amount or 0):.2f}", f"{float(e.caution_fee or 50000):.2f}", f"{float(e.total_amount or 0):.2f}",
                e.status, e.payment_status, assigned_name, e.created_at
            ])

        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=corporate_requests_report.csv'}
        )

    # -------------------------------------------------------------------------
    # ENTERPRISE AGENT REFERRAL MANAGEMENT MODULE
    # -------------------------------------------------------------------------
    @app.route('/admin/agents', methods=['GET'], endpoint='admin_panel.manage_agents')
    @admin_only
    def manage_agents():
        import uuid
        from datetime import datetime
        from sqlalchemy import or_
        from app.models import Agent, User, Commission, ReferralHistory, Booking

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        status_filter = request.args.get('status', '').strip().lower()
        search_query = request.args.get('search', '').strip()

        query = Agent.query.join(User, Agent.user_id == User.user_id)

        if status_filter and status_filter != 'all':
            query = query.filter(Agent.status == status_filter)

        if search_query:
            query = query.filter(
                or_(
                    Agent.agent_code.ilike(f"%{search_query}%"),
                    User.full_name.ilike(f"%{search_query}%"),
                    User.email.ilike(f"%{search_query}%"),
                    User.phone.ilike(f"%{search_query}%")
                )
            )

        pagination = query.order_by(Agent.registration_date.desc()).paginate(page=page, per_page=per_page, error_out=False)
        agents = pagination.items

        # Real-time Agent Analytics Calculation
        all_agents = Agent.query.all()
        total_registered = len(all_agents)
        active_count = len([a for a in all_agents if a.status == 'active'])
        pending_count = len([a for a in all_agents if a.status == 'pending'])
        suspended_count = len([a for a in all_agents if a.status == 'suspended'])

        all_commissions = Commission.query.all()
        total_earned = sum(float(c.commission_amount) for c in all_commissions)
        total_paid = sum(float(c.commission_amount) for c in all_commissions if c.commission_status == 'PAID')
        total_outstanding = sum(float(c.commission_amount) for c in all_commissions if c.commission_status in ['PENDING', 'APPROVED'])

        all_referrals_count = ReferralHistory.query.count()

        metrics = {
            'total_registered': total_registered,
            'active_count': active_count,
            'pending_count': pending_count,
            'suspended_count': suspended_count,
            'total_earned': total_earned,
            'total_paid': total_paid,
            'total_outstanding': total_outstanding,
            'total_referrals_count': all_referrals_count
        }

        # Calculate per-agent performance metrics
        agent_stats = {}
        for a in agents:
            a_comms = Commission.query.filter_by(agent_id=a.agent_id).all()
            earned = sum(float(c.commission_amount) for c in a_comms)
            paid = sum(float(c.commission_amount) for c in a_comms if c.commission_status == 'PAID')
            pending = sum(float(c.commission_amount) for c in a_comms if c.commission_status in ['PENDING', 'APPROVED'])
            
            ref_clicks = ReferralHistory.query.filter_by(agent_id=a.agent_id).count()
            successful_bookings = len([b for b in a.bookings if b.status in ['confirmed', 'checked_in', 'checked_out']])
            revenue_generated = sum(float(b.final_amount or b.total_price) for b in a.bookings if b.status in ['confirmed', 'checked_in', 'checked_out'])

            conversion_rate = round((successful_bookings / ref_clicks * 100), 1) if ref_clicks > 0 else 0.0

            # Badge logic
            if successful_bookings >= 20:
                badge = 'PLATINUM'
            elif successful_bookings >= 10:
                badge = 'GOLD'
            elif successful_bookings >= 5:
                badge = 'SILVER'
            else:
                badge = 'BRONZE'

            agent_stats[a.agent_id] = {
                'earned': earned,
                'paid': paid,
                'pending': pending,
                'clicks': ref_clicks,
                'bookings_count': successful_bookings,
                'revenue': revenue_generated,
                'conversion_rate': conversion_rate,
                'badge': badge
            }

        return render_template(
            'admin/manage_agents.html',
            agents=agents,
            pagination=pagination,
            metrics=metrics,
            agent_stats=agent_stats,
            status_filter=status_filter,
            search_query=search_query
        )

    @app.route('/admin/agents/<int:agent_id>/status', methods=['POST'], endpoint='admin_panel.update_agent_status')
    @admin_only
    def update_agent_status_route(agent_id):
        from app.models import Agent
        from app.extensions import db

        agent = Agent.query.get(agent_id)
        if not agent:
            flash('Agent profile not found.', 'danger')
            return redirect(url_for('admin_panel.manage_agents'))

        new_status = request.form.get('status', '').strip().lower()
        if new_status not in ['active', 'suspended', 'pending']:
            flash('Invalid agent status.', 'danger')
            return redirect(url_for('admin_panel.manage_agents'))

        old_status = agent.status
        agent.status = new_status
        db.session.commit()

        flash(f"Agent '{agent.user.full_name}' status updated from '{old_status}' to '{new_status}' successfully.", 'success')
        return redirect(url_for('admin_panel.manage_agents'))

    @app.route('/admin/agents/<int:agent_id>/reset_code', methods=['POST'], endpoint='admin_panel.reset_agent_code')
    @admin_only
    def reset_agent_code_route(agent_id):
        import uuid
        from app.models import Agent
        from app.extensions import db

        agent = Agent.query.get(agent_id)
        if not agent:
            flash('Agent profile not found.', 'danger')
            return redirect(url_for('admin_panel.manage_agents'))

        old_code = agent.agent_code
        new_code = f"AGT-THA-{uuid.uuid4().hex[:6].upper()}"
        agent.agent_code = new_code
        db.session.commit()

        flash(f"Referral Code for agent '{agent.user.full_name}' reset from '{old_code}' to '{new_code}' successfully.", 'success')
        return redirect(url_for('admin_panel.manage_agents'))

    @app.route('/admin/agents/<int:agent_id>/delete', methods=['POST'], endpoint='admin_panel.delete_agent')
    @admin_only
    def delete_agent_route(agent_id):
        from app.models import Agent
        from app.extensions import db

        if not current_user.is_superadmin:
            flash('Unauthorized. Only Super Admin can delete agent profiles.', 'danger')
            return redirect(url_for('admin_panel.manage_agents'))

        agent = Agent.query.get(agent_id)
        if not agent:
            flash('Agent profile not found.', 'danger')
            return redirect(url_for('admin_panel.manage_agents'))

        agent_name = agent.user.full_name
        agent.status = 'suspended'
        db.session.delete(agent)
        db.session.commit()

        flash(f"Agent '{agent_name}' deleted permanently by SuperAdmin.", 'warning')
        return redirect(url_for('admin_panel.manage_agents'))

    @app.route('/admin/agents/export', methods=['GET'], endpoint='admin_panel.export_agents')
    @admin_only
    def export_agents_route():
        import csv
        import io
        from flask import Response
        from app.models import Agent, Commission

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'Agent ID', 'Full Name', 'Referral Code', 'Email', 'Phone',
            'Bank Name', 'Account Number', 'Status', 'Total Referrals',
            'Successful Bookings', 'Total Earnings (NGN)', 'Commission Paid (NGN)',
            'Outstanding Balance (NGN)', 'Registration Date'
        ])

        agents = Agent.query.order_by(Agent.registration_date.desc()).all()
        for a in agents:
            a_comms = Commission.query.filter_by(agent_id=a.agent_id).all()
            earned = sum(float(c.commission_amount) for c in a_comms)
            paid = sum(float(c.commission_amount) for c in a_comms if c.commission_status == 'PAID')
            pending = sum(float(c.commission_amount) for c in a_comms if c.commission_status in ['PENDING', 'APPROVED'])
            succ_b = len([b for b in a.bookings if b.status in ['confirmed', 'checked_in', 'checked_out']])

            writer.writerow([
                f"AGT-{a.agent_id}", a.user.full_name if a.user else 'N/A', a.agent_code,
                a.user.email if a.user else 'N/A', a.user.phone if a.user else 'N/A',
                a.bank_name or 'N/A', a.account_number or 'N/A', a.status,
                len(a.bookings), succ_b, f"{earned:.2f}", f"{paid:.2f}", f"{pending:.2f}",
                a.registration_date
            ])

        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=agent_referrals_report.csv'}
        )

    # -------------------------------------------------------------------------
    # ENTERPRISE REVIEW MANAGEMENT MODULE
    # -------------------------------------------------------------------------
    @app.route('/admin/reviews', methods=['GET'], endpoint='admin_panel.manage_reviews')
    @admin_only
    def manage_reviews():
        from sqlalchemy import or_
        from app.models import Review, Apartment, AuditLog

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        status_filter = request.args.get('status', '').strip().lower()
        rating_filter = request.args.get('rating', type=int)
        apartment_filter = request.args.get('apartment_id', type=int)
        search_query = request.args.get('search', '').strip()

        query = Review.query

        if status_filter and status_filter != 'all':
            if status_filter == 'published':
                query = query.filter(Review.is_public == True)
            elif status_filter == 'hidden':
                query = query.filter(Review.is_public == False)
            else:
                query = query.filter(Review.status.ilike(status_filter))

        if rating_filter:
            query = query.filter(Review.rating == rating_filter)

        if apartment_filter:
            query = query.filter(Review.apartment_id == apartment_filter)

        if search_query:
            query = query.filter(
                or_(
                    Review.title.ilike(f"%{search_query}%"),
                    Review.comment.ilike(f"%{search_query}%")
                )
            )

        pagination = query.order_by(Review.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        reviews = pagination.items

        # Real-time Metrics Calculation
        all_reviews = Review.query.all()
        total_reviews = len(all_reviews)
        published_reviews = len([r for r in all_reviews if r.is_public])
        hidden_reviews = len([r for r in all_reviews if not r.is_public])
        pending_reviews = len([r for r in all_reviews if r.status == 'pending'])
        reported_reviews = len([r for r in all_reviews if r.status == 'reported'])
        avg_rating = round(sum(r.rating for r in all_reviews) / total_reviews, 1) if total_reviews > 0 else 5.0

        metrics = {
            'total_reviews': total_reviews,
            'published_reviews': published_reviews,
            'hidden_reviews': hidden_reviews,
            'pending_reviews': pending_reviews,
            'reported_reviews': reported_reviews,
            'avg_rating': avg_rating
        }

        apartments = Apartment.query.all()

        return render_template(
            'admin/manage_reviews.html',
            reviews=reviews,
            pagination=pagination,
            metrics=metrics,
            apartments=apartments,
            status_filter=status_filter,
            rating_filter=rating_filter,
            apartment_filter=apartment_filter,
            search_query=search_query
        )

    @app.route('/admin/reviews/<int:review_id>/toggle_visibility', methods=['POST'], endpoint='admin_panel.toggle_review_visibility')
    @admin_only
    def toggle_review_visibility_route(review_id):
        from app.models import Review, AuditLog
        from app.extensions import db

        review = Review.query.get(review_id)
        if not review:
            flash('Review record not found.', 'danger')
            return redirect(url_for('admin_panel.manage_reviews'))

        review.is_public = not review.is_public
        review.status = 'published' if review.is_public else 'hidden'

        action_name = 'RESTORE_REVIEW_VISIBILITY' if review.is_public else 'HIDE_REVIEW_VISIBILITY'
        audit = AuditLog(
            user_id=current_user.user_id,
            activity_type='REVIEW_MODERATION',
            description=f"Review #{review_id} visibility set to {'Public' if review.is_public else 'Hidden'}",
            module='REVIEWS',
            action=action_name,
            ip_address=request.remote_addr
        )
        db.session.add(audit)
        db.session.commit()

        status_msg = 'restored to public view' if review.is_public else 'hidden from public view (retained in database)'
        flash(f"Review #{review_id} {status_msg} successfully.", 'success')
        return redirect(url_for('admin_panel.manage_reviews'))

    @app.route('/admin/reviews/<int:review_id>/status', methods=['POST'], endpoint='admin_panel.update_review_status')
    @admin_only
    def update_review_status_route(review_id):
        from app.models import Review, AuditLog
        from app.extensions import db

        review = Review.query.get(review_id)
        if not review:
            flash('Review not found.', 'danger')
            return redirect(url_for('admin_panel.manage_reviews'))

        new_status = request.form.get('status', '').strip().lower()
        old_status = review.status
        review.status = new_status

        if new_status in ['published', 'approved']:
            review.is_public = True
        elif new_status in ['hidden', 'archived', 'reported']:
            review.is_public = False

        audit = AuditLog(
            user_id=current_user.user_id,
            activity_type='REVIEW_STATUS_UPDATE',
            description=f"Review #{review_id} status changed from '{old_status}' to '{new_status}'",
            module='REVIEWS',
            action=f"SET_STATUS_{new_status.upper()}",
            ip_address=request.remote_addr
        )
        db.session.add(audit)
        db.session.commit()

        flash(f"Review #{review_id} status updated to '{new_status}' successfully.", 'success')
        return redirect(url_for('admin_panel.manage_reviews'))

    @app.route('/admin/reviews/<int:review_id>/reply', methods=['POST'], endpoint='admin_panel.reply_to_review')
    @admin_only
    def reply_to_review_route(review_id):
        from datetime import datetime
        from app.models import Review, ReviewResponse, AuditLog
        from app.extensions import db

        review = Review.query.get(review_id)
        if not review:
            flash('Review not found.', 'danger')
            return redirect(url_for('admin_panel.manage_reviews'))

        response_text = request.form.get('response', '').strip()
        if not response_text:
            flash('Response text cannot be empty.', 'warning')
            return redirect(url_for('admin_panel.manage_reviews'))

        if review.response:
            review.response.response = response_text
            review.response.admin_id = current_user.user_id
            review.response.created_at = datetime.utcnow()
        else:
            rr = ReviewResponse(
                review_id=review_id,
                admin_id=current_user.user_id,
                response=response_text
            )
            db.session.add(rr)

        audit = AuditLog(
            user_id=current_user.user_id,
            activity_type='REVIEW_RESPONSE',
            description=f"Admin replied to Review #{review_id}",
            module='REVIEWS',
            action='POST_REVIEW_RESPONSE',
            ip_address=request.remote_addr
        )
        db.session.add(audit)
        db.session.commit()

        flash(f"Official response posted for Review #{review_id} successfully!", 'success')
        return redirect(url_for('admin_panel.manage_reviews'))

    @app.route('/admin/reviews/export', methods=['GET'], endpoint='admin_panel.export_reviews')
    @admin_only
    def export_reviews_route():
        import csv
        import io
        from flask import Response
        from app.models import Review

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'Review ID', 'Booking Reference', 'Customer Name', 'Customer Email',
            'Apartment Title', 'Rating', 'Title', 'Comment',
            'Is Visible Publicly', 'Status', 'Submitted Date'
        ])

        reviews = Review.query.order_by(Review.created_at.desc()).all()
        for r in reviews:
            c_name = r.user.full_name if r.user else 'Guest'
            c_email = r.user.email if r.user else 'N/A'
            b_ref = r.booking.booking_ref if r.booking else 'N/A'
            apt_title = r.apartment.title if r.apartment else 'N/A'

            writer.writerow([
                f"REV-{r.review_id}", b_ref, c_name, c_email,
                apt_title, r.rating, r.title or '', r.comment or '',
                'Yes' if r.is_public else 'No', r.status, r.created_at
            ])

        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=customer_reviews_report.csv'}
        )

    # -------------------------------------------------------------------------
    # ENTERPRISE ROOM INSPECTION & CAUTION FEE REFUND MODULE
    # -------------------------------------------------------------------------
    @app.route('/admin/inspections', methods=['GET'], endpoint='admin_panel.manage_inspections')
    @admin_only
    def manage_inspections():
        from sqlalchemy import or_
        from app.models import Inspection, Refund, Booking, AuditLog

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        status_filter = request.args.get('status', '').strip().lower()
        search_query = request.args.get('search', '').strip()

        query = Inspection.query.join(Booking)

        if status_filter and status_filter != 'all':
            query = query.filter(Inspection.approval_status == status_filter)

        if search_query:
            query = query.filter(
                or_(
                    Booking.booking_ref.ilike(f"%{search_query}%"),
                    Booking.guest_name.ilike(f"%{search_query}%"),
                    Booking.guest_email.ilike(f"%{search_query}%")
                )
            )

        pagination = query.order_by(Inspection.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        inspections = pagination.items

        all_inspections = Inspection.query.all()
        total_inspections = len(all_inspections)
        passed_inspections = len([i for i in all_inspections if not i.damage_found])
        pending_reviews = len([i for i in all_inspections if i.approval_status == 'pending'])
        damage_claims = len([i for i in all_inspections if i.damage_found])

        all_refunds = Refund.query.all()
        total_refunded = sum(float(r.refund_amount) for r in all_refunds if r.refund_status == 'processed')
        total_deductions = sum(float(i.estimated_repair_cost) for i in all_inspections if i.damage_found)

        metrics = {
            'total_inspections': total_inspections,
            'passed_inspections': passed_inspections,
            'pending_reviews': pending_reviews,
            'damage_claims': damage_claims,
            'total_refunded': total_refunded,
            'total_deductions': total_deductions
        }

        # Active checked-out/confirmed bookings eligible for inspection
        eligible_bookings = Booking.query.filter(Booking.status.in_(['checked_out', 'confirmed', 'checked_in'])).all()

        return render_template(
            'admin/manage_inspections.html',
            inspections=inspections,
            pagination=pagination,
            metrics=metrics,
            eligible_bookings=eligible_bookings,
            status_filter=status_filter,
            search_query=search_query
        )

    @app.route('/admin/inspections/submit', methods=['POST'], endpoint='admin_panel.submit_inspection')
    @admin_only
    def submit_inspection_route():
        from datetime import datetime
        from app.models import Inspection, Booking, AuditLog
        from app.extensions import db

        booking_id = request.form.get('booking_id', type=int)
        if not booking_id:
            flash('Please select a valid booking reference.', 'danger')
            return redirect(url_for('admin_panel.manage_inspections'))

        booking = Booking.query.get(booking_id)
        if not booking:
            flash('Booking record not found.', 'danger')
            return redirect(url_for('admin_panel.manage_inspections'))

        damage_found = request.form.get('damage_found') == 'true'
        damage_desc = request.form.get('damage_description', '').strip()
        repair_cost = float(request.form.get('estimated_repair_cost', 0.00)) if damage_found else 0.00

        inspection = Inspection(
            booking_id=booking_id,
            inspector_id=current_user.user_id,
            property_condition=request.form.get('property_condition', 'excellent'),
            furniture_status=request.form.get('furniture_status', 'good'),
            electronics_status=request.form.get('electronics_status', 'good'),
            kitchen_status=request.form.get('kitchen_status', 'good'),
            bathroom_status=request.form.get('bathroom_status', 'good'),
            keys_status=request.form.get('keys_status', 'returned'),
            remotes_status=request.form.get('remotes_status', 'returned'),
            damage_found=damage_found,
            damage_description=damage_desc,
            estimated_repair_cost=repair_cost,
            recommendation='partial_refund' if damage_found else 'full_refund',
            approval_status='pending'
        )
        db.session.add(inspection)

        audit = AuditLog(
            user_id=current_user.user_id,
            activity_type='ROOM_INSPECTION_SUBMIT',
            description=f"Inspection report submitted for Booking {booking.booking_ref} (Damage Found: {damage_found})",
            module='INSPECTIONS',
            action='CREATE_ROOM_INSPECTION',
            ip_address=request.remote_addr
        )
        db.session.add(audit)
        db.session.commit()

        # Trigger SuperAdmin Notification for Inspection Report
        from app.services import NotificationService
        if damage_found:
            NotificationService.create_notification(
                notification_type='PROPERTY_DAMAGE_REPORTED',
                portal='INSPECTIONS',
                title='Room Inspection - Property Damage Reported',
                message=f"Checkout inspection for Booking #{booking.booking_ref} reported property damage (Est. Repair: NGN {repair_cost:,.2f}). Caution fee deduction decision required.",
                priority='CRITICAL',
                requires_action=True,
                related_type='Inspection',
                related_id=inspection.inspection_id,
                action_url=url_for('admin_panel.manage_inspections')
            )
        else:
            NotificationService.create_notification(
                notification_type='ROOM_INSPECTION_COMPLETED',
                portal='INSPECTIONS',
                title='Room Inspection Completed',
                message=f"Checkout inspection for Booking #{booking.booking_ref} completed with zero damage found.",
                priority='LOW',
                requires_action=False,
                related_type='Inspection',
                related_id=inspection.inspection_id,
                action_url=url_for('admin_panel.manage_inspections')
            )

        flash(f"Room Inspection report submitted for Booking {booking.booking_ref} successfully!", 'success')
        return redirect(url_for('admin_panel.manage_inspections'))

    @app.route('/admin/inspections/<int:inspection_id>/approve', methods=['POST'], endpoint='admin_panel.approve_inspection')
    @admin_only
    def approve_inspection_route(inspection_id):
        from datetime import datetime
        from app.models import Inspection, Refund, Booking, Payment, AuditLog
        from app.extensions import db

        inspection = Inspection.query.get(inspection_id)
        if not inspection:
            flash('Inspection record not found.', 'danger')
            return redirect(url_for('admin_panel.manage_inspections'))

        booking = Booking.query.get(inspection.booking_id)
        payment = Payment.query.filter_by(booking_id=booking.booking_id).first()

        caution_liability = float(booking.caution_fee_amount or booking.caution_fee or 50000.00)
        repair_cost = float(inspection.estimated_repair_cost or 0.00)

        if not inspection.damage_found or inspection.recommendation == 'full_refund':
            net_refund = caution_liability
            refund_type = 'full'
            refund_reason = 'Full refundable caution fee approved. Room passed checkout inspection with zero damage.'
        else:
            net_refund = max(0.0, caution_liability - repair_cost)
            refund_type = 'partial' if net_refund > 0 else 'none'
            refund_reason = f"Partial caution fee refund processed after deducting estimated repair cost of NGN {repair_cost:,.2f} for damage: {inspection.damage_description}"

        # Create Refund Record
        refund = Refund(
            booking_id=booking.booking_id,
            payment_id=payment.payment_id if payment else None,
            inspection_id=inspection_id,
            approved_by=current_user.user_id,
            refund_amount=net_refund,
            refund_reason=refund_reason,
            refund_type=refund_type,
            refund_status='processed',
            approved_at=datetime.utcnow(),
            processed_at=datetime.utcnow()
        )
        db.session.add(refund)

        inspection.approval_status = 'approved'
        booking.status = 'completed'

        audit = AuditLog(
            user_id=current_user.user_id,
            activity_type='CAUTION_FEE_REFUND',
            description=f"Approved caution fee refund of NGN {net_refund:,.2f} for Booking {booking.booking_ref} (Inspection #{inspection_id})",
            module='REFUNDS',
            action='APPROVE_CAUTION_REFUND',
            ip_address=request.remote_addr
        )
        db.session.add(audit)
        db.session.commit()

        flash(f"Caution Fee Refund of NGN {net_refund:,.2f} approved and processed for Booking {booking.booking_ref}!", 'success')
        return redirect(url_for('admin_panel.manage_inspections'))

    @app.route('/admin/inspections/export', methods=['GET'], endpoint='admin_panel.export_inspections')
    @admin_only
    def export_inspections_route():
        import csv
        import io
        from flask import Response
        from app.models import Inspection

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'Inspection ID', 'Booking Reference', 'Guest Name', 'Apartment',
            'Property Condition', 'Furniture Status', 'Electronics Status',
            'Damage Found', 'Repair Cost (NGN)', 'Recommendation', 'Approval Status', 'Submitted Date'
        ])

        inspections = Inspection.query.order_by(Inspection.created_at.desc()).all()
        for i in inspections:
            b_ref = i.booking.booking_ref if i.booking else 'N/A'
            g_name = i.booking.guest_name if i.booking else 'N/A'
            apt_title = i.booking.apartment.title if (i.booking and i.booking.apartment) else 'N/A'

            writer.writerow([
                f"INSP-{i.inspection_id}", b_ref, g_name, apt_title,
                i.property_condition, i.furniture_status, i.electronics_status,
                'Yes' if i.damage_found else 'No', f"{float(i.estimated_repair_cost or 0):.2f}",
                i.recommendation, i.approval_status, i.created_at
            ])

        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=room_inspections_report.csv'}
        )

    @app.route('/admin/apartments/gallery', methods=['GET', 'POST'], endpoint='admin_panel.manage_gallery')
    @admin_only
    def manage_gallery():
        from flask import current_app, jsonify
        from app.models import Apartment, ApartmentImage
        from werkzeug.utils import secure_filename
        import os, uuid

        is_ajax = request.is_json or request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        if request.method == 'POST':
            apartment_id = request.form.get('apartment_id')
            if not apartment_id:
                msg = 'Please select an apartment suite.'
                if is_ajax:
                    return jsonify({'success': False, 'message': msg}), 400
                flash(msg, 'danger')
                return redirect(url_for('admin_panel.manage_gallery'))

            apartment = Apartment.query.get(apartment_id)
            if not apartment:
                msg = 'Selected apartment does not exist.'
                if is_ajax:
                    return jsonify({'success': False, 'message': msg}), 404
                flash(msg, 'danger')
                return redirect(url_for('admin_panel.manage_gallery'))

            uploaded_files = request.files.getlist('images')
            if not uploaded_files or not uploaded_files[0].filename:
                msg = 'Please select at least one valid image file to upload.'
                if is_ajax:
                    return jsonify({'success': False, 'message': msg}), 400
                flash(msg, 'warning')
                return redirect(url_for('admin_panel.manage_gallery'))

            allowed_extensions = {'png', 'jpg', 'jpeg', 'webp'}
            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'properties')
            os.makedirs(upload_dir, exist_ok=True)

            success_count = 0
            rejected_count = 0
            for file in uploaded_files:
                if not file or not file.filename:
                    continue
                
                raw_filename = secure_filename(file.filename) or 'image.jpg'
                ext = raw_filename.rsplit('.', 1)[-1].lower() if '.' in raw_filename else ''
                if ext not in allowed_extensions or not file.mimetype.startswith('image/'):
                    rejected_count += 1
                    continue

                safe_name = f"prop_{apartment_id}_{uuid.uuid4().hex[:8]}.{ext}"
                file_path = os.path.join(upload_dir, safe_name)
                file.save(file_path)

                rel_url = f"uploads/properties/{safe_name}"
                apt_service.add_apartment_image(
                    apartment_id=apartment_id,
                    image_url=rel_url,
                    user_id=current_user.user_id
                )
                success_count += 1

            if success_count > 0:
                if rejected_count > 0:
                    msg = f"Successfully uploaded {success_count} image(s) for '{apartment.display_title}'. Note: {rejected_count} file(s) were rejected due to invalid format."
                else:
                    msg = f"Successfully uploaded {success_count} image(s) for '{apartment.display_title}'!"
                if is_ajax:
                    return jsonify({'success': True, 'message': msg, 'count': success_count, 'rejected': rejected_count}), 200
                flash(msg, 'warning' if rejected_count > 0 else 'success')
            else:
                msg = f"Upload failed: All selected files ({rejected_count}) were rejected. Allowed formats: JPEG, PNG, WEBP."
                if is_ajax:
                    return jsonify({'success': False, 'message': msg}), 400
                flash(msg, 'danger')

            return redirect(url_for('admin_panel.manage_gallery'))

        apartments = Apartment.query.all()
        return render_template('admin_panel/manage_gallery.html', apartments=apartments)

    @app.route('/admin/apartments/images/<int:image_id>/delete', methods=['POST'], endpoint='admin_panel.delete_image')
    @admin_only
    def delete_image(image_id):
        from flask import jsonify
        is_ajax = request.is_json or request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        ok, msg = apt_service.delete_apartment_image(image_id)
        if is_ajax:
            return jsonify({'success': ok, 'message': msg}), (200 if ok else 400)
        if ok:
            flash(msg, 'success')
        else:
            flash(msg, 'danger')
        return redirect(url_for('admin_panel.manage_gallery'))

    @app.route('/admin/apartments/images/<int:image_id>/set_cover', methods=['POST'], endpoint='admin_panel.set_cover_image')
    @admin_only
    def set_cover_image_route(image_id):
        from flask import jsonify
        is_ajax = request.is_json or request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        ok, msg = apt_service.set_cover_image(image_id)
        if is_ajax:
            return jsonify({'success': ok, 'message': msg}), (200 if ok else 400)
        if ok:
            flash(msg, 'success')
        else:
            flash(msg, 'danger')
        return redirect(url_for('admin_panel.manage_gallery'))
