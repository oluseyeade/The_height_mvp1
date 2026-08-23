from flask import render_template, request, flash, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from app.forms import LoginForm, RegisterForm
from app.services import UserService

user_service = UserService()

def init_auth_routes(app):
    @app.route('/auth/login', methods=['GET', 'POST'], endpoint='auth.login')
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('public.index'))

        form = LoginForm()
        if form.validate_on_submit():
            user, msg = user_service.authenticate(form.email.data, form.password.data)
            if user:
                if getattr(user, 'is_superadmin', False) or getattr(user, 'is_admin', False):
                    flash('Please use the administrator login portal.', 'danger')
                    return render_template('auth/login.html', form=form)

                login_user(user, remember=form.remember.data)
                flash(f'Successfully logged in. Welcome back, {user.full_name}!', 'success')
                next_page = request.args.get('next')
                return redirect(next_page or url_for('public.index'))
            else:
                flash(msg, 'danger')

        return render_template('auth/login.html', form=form)

    @app.route('/auth/register', methods=['GET', 'POST'], endpoint='auth.register')
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('public.index'))

        form = RegisterForm()
        if form.validate_on_submit():
            user, msg = user_service.register_user(
                full_name=form.full_name.data,
                email=form.email.data,
                phone=form.phone.data,
                password=form.password.data,
                role_name='Customer'
            )
            if user:
                flash(f"Welcome {user.full_name}", 'success')
                return redirect(url_for('auth.login'))
            else:
                flash(msg, 'danger')

        return render_template('auth/register.html', form=form)

    @app.route('/auth/logout', endpoint='auth.logout')
    @login_required
    def logout():
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('public.index'))

    @app.route('/auth/profile', endpoint='auth.profile')
    @login_required
    def profile():
        from app.models import Booking, Payment, Receipt
        from app.extensions import db

        # Auto-link legacy unlinked bookings matching current_user.email
        if current_user.email:
            unlinked = Booking.query.filter(Booking.user_id.is_(None), Booking.guest_email == current_user.email).all()
            if unlinked:
                for ub in unlinked:
                    ub.user_id = current_user.user_id
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()

        # Retrieve user's complete booking history
        user_bookings = Booking.query.filter_by(user_id=current_user.user_id).order_by(Booking.created_at.desc()).all()

        # Summary statistics
        stats = {
            'total': len(user_bookings),
            'confirmed': sum(1 for b in user_bookings if (b.status and b.status.lower() in ['confirmed', 'paid']) or (b.payment_status and b.payment_status.upper() in ['PAID', 'VERIFIED'])),
            'pending': sum(1 for b in user_bookings if b.payment_status and b.payment_status.upper() in ['PENDING', 'PENDING_PAYMENT']),
            'completed': sum(1 for b in user_bookings if b.status and b.status.lower() == 'completed'),
            'cancelled': sum(1 for b in user_bookings if b.status and b.status.lower() in ['cancelled', 'expired', 'timed_out'])
        }

        # Map booking_id to receipt for direct receipt download
        booking_ids = [b.booking_id for b in user_bookings]
        payments = Payment.query.filter(Payment.booking_id.in_(booking_ids)).all() if booking_ids else []
        payment_ids = [p.payment_id for p in payments]
        receipts = Receipt.query.filter(Receipt.payment_id.in_(payment_ids)).all() if payment_ids else []
        
        receipts_by_booking = {}
        for p in payments:
            rcp = next((r for r in receipts if r.payment_id == p.payment_id), None)
            if rcp:
                receipts_by_booking[p.booking_id] = rcp

        return render_template(
            'auth/profile.html',
            bookings=user_bookings,
            stats=stats,
            receipts_map=receipts_by_booking
        )
