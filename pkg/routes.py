import json
import os

from flask import Flask, Response, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user
from jinja2 import ChoiceLoader, FileSystemLoader

from pkg.agents.forms import AgentRegistrationForm
from pkg.apartments.forms import ApartmentForm, MultipleImageUploadForm
from pkg.auth.forms import LoginForm, RegistrationForm
from pkg.bookings.forms import BookingRequestForm
from pkg.corporate.forms import CorporateEnquiryForm, QuoteGeneratorForm
from pkg.decorators.role_required import admin_only, agent_only, superadmin_only
from pkg.extensions import db
from pkg.models.audit_log import AuditLog
from pkg.models.booking import Booking
from pkg.models.user import Role, User
from pkg.payments.forms import PaymentProofForm
from pkg.repositories.booking_repository import BookingRepository
from pkg.reviews.forms import ReviewForm
from pkg.services.agent_service import AgentService
from pkg.services.apartment_service import ApartmentService
from pkg.services.booking_service import BookingService
from pkg.services.corporate_service import CorporateService
from pkg.services.dashboard_service import DashboardService
from pkg.services.payment_service import PaymentService
from pkg.services.report_service import ReportService
from pkg.services.review_service import ReviewService
from pkg.services.user_service import UserService


booking_repo = BookingRepository()
apt_service = ApartmentService()
booking_service = BookingService()
payment_service = PaymentService()
corp_service = CorporateService()
review_service = ReviewService()
agent_service = AgentService()
user_service = UserService()


def _register_template_paths(app: Flask) -> None:
    base_dir = os.path.dirname(__file__)
    search_paths = [
        os.path.join(base_dir, 'templates'),
        os.path.join(base_dir, 'admin_panel', 'templates'),
        os.path.join(base_dir, 'agents', 'templates'),
        os.path.join(base_dir, 'apartments', 'templates'),
        os.path.join(base_dir, 'auth', 'templates'),
        os.path.join(base_dir, 'availability', 'templates'),
        os.path.join(base_dir, 'bookings', 'templates'),
        os.path.join(base_dir, 'corporate', 'templates'),
        os.path.join(base_dir, 'payments', 'templates'),
        os.path.join(base_dir, 'public', 'templates'),
        os.path.join(base_dir, 'receipts', 'templates'),
        os.path.join(base_dir, 'reports', 'templates'),
        os.path.join(base_dir, 'reviews', 'templates'),
        os.path.join(base_dir, 'superadmin_panel', 'templates'),
    ]

    loaders = [FileSystemLoader(path) for path in search_paths if os.path.isdir(path)]
    app.jinja_loader = ChoiceLoader(loaders)
    app.jinja_env.loader = app.jinja_loader


def register_routes(app: Flask) -> None:
    _register_template_paths(app)

    @app.route('/', endpoint='public.index')
    def public_index():
        featured_apartments = [
            {
                'id': 1,
                'title': 'The king',
                'category': 'apartment',
                'bedrooms': 3,
                'bathrooms': 3,
                'capacity': 6,
                'price': 180000,
                'image': 'https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?auto=format&fit=crop&w=800&q=80',
                'tag': 'Featured Luxury'
            },
            {
                'id': 2,
                'title': 'Executive Oceanfront Loft',
                'category': 'Executive',
                'bedrooms': 2,
                'bathrooms': 2,
                'capacity': 4,
                'price': 95000,
                'image': 'https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&fit=crop&w=800&q=80',
                'tag': 'Best Value'
            },
            {
                'id': 3,
                'title': 'Deluxe Ambassador Suite',
                'category': 'Deluxe',
                'bedrooms': 2,
                'bathrooms': 2,
                'capacity': 4,
                'price': 110000,
                'image': 'https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=800&q=80',
                'tag': 'Popular'
            },
            {
                'id': 4,
                'title': 'Studio Modern Elegance',
                'category': 'Studio',
                'bedrooms': 1,
                'bathrooms': 1,
                'capacity': 2,
                'price': 65000,
                'image': 'https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=800&q=80',
                'tag': 'Cozy'
            }
        ]
        return render_template('public/index.html', title='The Height Apartment - Luxury Living & Shortlet Suites', apartments=featured_apartments)

    app.add_url_rule('/auth/login', endpoint='auth.login', view_func=login, methods=['GET', 'POST'])
    app.add_url_rule('/auth/register', endpoint='auth.register', view_func=register, methods=['GET', 'POST'])
    app.add_url_rule('/auth/logout', endpoint='auth.logout', view_func=logout, methods=['GET'])
    app.add_url_rule('/contact', endpoint='public.contact', view_func=contact_us, methods=['GET'])

    app.add_url_rule('/apartments/', endpoint='apartments.list_apartments', view_func=list_apartments, methods=['GET'])
    app.add_url_rule('/apartments/<int:apartment_id>', endpoint='apartments.detail_apartment', view_func=detail_apartment, methods=['GET'])
    app.add_url_rule('/apartments/manage', endpoint='apartments.manage_apartments', view_func=manage_apartments, methods=['GET'])
    app.add_url_rule('/apartments/create', endpoint='apartments.create_apartment', view_func=create_apartment, methods=['GET', 'POST'])
    app.add_url_rule('/apartments/<int:apartment_id>/edit', endpoint='apartments.edit_apartment', view_func=edit_apartment, methods=['GET', 'POST'])
    app.add_url_rule('/apartments/<int:apartment_id>/images', endpoint='apartments.upload_images', view_func=upload_images, methods=['GET', 'POST'])

    app.add_url_rule('/bookings/create/<int:apartment_id>', endpoint='bookings.create_booking', view_func=create_booking, methods=['GET', 'POST'])
    app.add_url_rule('/bookings/ref/<booking_ref>', endpoint='bookings.detail_booking', view_func=detail_booking, methods=['GET'])
    app.add_url_rule('/bookings/my-bookings', endpoint='bookings.list_user_bookings', view_func=list_user_bookings, methods=['GET'])
    app.add_url_rule('/bookings/manage', endpoint='bookings.manage_bookings', view_func=manage_bookings, methods=['GET'])

    app.add_url_rule('/availability/calendar/<int:apartment_id>', endpoint='availability.calendar_view', view_func=calendar_view, methods=['GET'])
    app.add_url_rule('/availability/api/events/<int:apartment_id>', endpoint='availability.availability_events', view_func=availability_events, methods=['GET'])

    app.add_url_rule('/payments/pay/<booking_ref>', endpoint='payments.submit_payment', view_func=submit_payment, methods=['GET', 'POST'])
    app.add_url_rule('/payments/paystack/callback/<reference>', endpoint='payments.paystack_callback', view_func=paystack_callback, methods=['GET'])
    app.add_url_rule('/payments/paystack/webhook', endpoint='payments.paystack_webhook', view_func=paystack_webhook, methods=['POST'])
    app.add_url_rule('/payments/manage', endpoint='payments.manage_payments', view_func=manage_payments, methods=['GET'])
    app.add_url_rule('/payments/verify/<int:payment_id>', endpoint='payments.verify_payment', view_func=verify_payment, methods=['POST'])

    app.add_url_rule('/corporate/', endpoint='corporate.corporate_index', view_func=corporate_index, methods=['GET'])
    app.add_url_rule('/corporate/request-quote', endpoint='corporate.request_quote', view_func=request_quote, methods=['GET', 'POST'])
    app.add_url_rule('/corporate/manage', endpoint='corporate.manage_enquiries', view_func=manage_enquiries, methods=['GET'])
    app.add_url_rule('/corporate/quote/create/<int:enquiry_id>', endpoint='corporate.create_quote', view_func=create_quote, methods=['GET', 'POST'])
    app.add_url_rule('/corporate/quote/<quote_number>', endpoint='corporate.view_quote', view_func=view_quote, methods=['GET'])

    app.add_url_rule('/receipts/view/<booking_ref>', endpoint='receipts.view_receipt', view_func=view_receipt, methods=['GET'])
    app.add_url_rule('/receipts/download/<booking_ref>', endpoint='receipts.download_pdf', view_func=download_pdf, methods=['GET'])

    app.add_url_rule('/reports/', endpoint='reports.index', view_func=index_reports, methods=['GET'])
    app.add_url_rule('/reports/export/bookings/csv', endpoint='reports.export_bookings_csv', view_func=export_bookings_csv, methods=['GET'])

    app.add_url_rule('/agent/register', endpoint='agents.register', view_func=register_agent, methods=['GET', 'POST'])
    app.add_url_rule('/agent/dashboard', endpoint='agents.dashboard', view_func=dashboard_agent, methods=['GET'])
    app.add_url_rule('/agent/profile', endpoint='agents.profile', view_func=profile_agent, methods=['GET'])
    app.add_url_rule('/agent/commissions', endpoint='agents.commission_history', view_func=commission_history, methods=['GET'])
    app.add_url_rule('/agent/bookings', endpoint='agents.agent_bookings', view_func=agent_bookings, methods=['GET'])

    app.add_url_rule('/reviews/write/<booking_ref>', endpoint='reviews.write_review', view_func=write_review, methods=['GET', 'POST'])
    app.add_url_rule('/reviews/suite/<int:apartment_id>', endpoint='reviews.view_suite_reviews', view_func=view_suite_reviews, methods=['GET'])

    app.add_url_rule('/admin/', endpoint='admin_panel.dashboard', view_func=dashboard_admin, methods=['GET'])
    app.add_url_rule('/admin/dashboard', endpoint='admin_panel.dashboard', view_func=dashboard_admin, methods=['GET'])

    app.add_url_rule('/superadmin/', endpoint='superadmin_panel.dashboard', view_func=dashboard_superadmin, methods=['GET'])
    app.add_url_rule('/superadmin/dashboard', endpoint='superadmin_panel.dashboard', view_func=dashboard_superadmin, methods=['GET'])
    app.add_url_rule('/superadmin/audit-logs', endpoint='superadmin_panel.audit_logs', view_func=audit_logs, methods=['GET'])
    app.add_url_rule('/superadmin/users', endpoint='superadmin_panel.user_management', view_func=user_management, methods=['GET'])


# Route functions below

def contact_us():
    return redirect(url_for('corporate.request_quote'))


def login():
    if current_user.is_authenticated:
        return redirect(url_for('public.index'))

    form = LoginForm()
    if form.validate_on_submit():
        success, message, user = user_service.authenticate(form.email.data, form.password.data)
        if success:
            flash(message, 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('public.index'))
        else:
            flash(message, 'danger')

    return render_template('login.html', form=form, title='Sign In - The Height Apartment')


def register():
    if current_user.is_authenticated:
        return redirect(url_for('public.index'))

    form = RegistrationForm()
    if form.validate_on_submit():
        success, message, user = user_service.register_user(
            full_name=form.full_name.data,
            email=form.email.data,
            password=form.password.data,
            phone=form.phone.data,
            role_name='User'
        )
        if success:
            flash(message, 'success')
            return redirect(url_for('auth.login'))
        else:
            flash(message, 'danger')

    return render_template('register.html', form=form, title='Register Account - The Height Apartment')


def logout():
    user_service.logout_current_user(current_user)
    flash('You have been logged out safely.', 'info')
    return redirect(url_for('public.index'))


def list_apartments():
    categories = apt_service.get_categories()
    category_id = request.args.get('category_id', type=int)

    if category_id:
        apartments = apt_service.apt_repo.find_by_category(category_id)
    else:
        apartments = apt_service.get_available_apartments()

    return render_template('list.html', apartments=apartments, categories=categories, selected_category=category_id, title="Suites & Apartments - The Height Apartment")


def detail_apartment(apartment_id):
    apartment = apt_service.get_apartment_by_id(apartment_id, increment_views=True)
    if not apartment:
        flash("Apartment suite not found.", "warning")
        return redirect(url_for('apartments.list_apartments'))

    return render_template('detail.html', apartment=apartment, title=f"{apartment.title} - The Height Apartment")


@admin_only
def manage_apartments():
    apartments = apt_service.get_all_apartments()
    return render_template('manage.html', apartments=apartments, title="Apartment Management - Admin")


@admin_only
def create_apartment():
    form = ApartmentForm()
    categories = apt_service.get_categories()
    form.category_id.choices = [(c.category_id, c.name) for c in categories]

    if form.validate_on_submit():
        success, message, apartment = apt_service.create_apartment(
            title=form.title.data,
            description=form.description.data,
            price_per_night=form.price_per_night.data,
            category_id=form.category_id.data,
            bedrooms=form.bedrooms.data,
            bathrooms=form.bathrooms.data,
            capacity=form.capacity.data,
            square_feet=form.square_feet.data,
            admin_user_id=current_user.user_id
        )
        if success:
            flash(message, 'success')
            return redirect(url_for('apartments.upload_images', apartment_id=apartment.apartment_id))
        else:
            flash(message, 'danger')

    return render_template('create.html', form=form, title="Create New Suite - Admin")


@admin_only
def edit_apartment(apartment_id):
    apartment = apt_service.get_apartment_by_id(apartment_id)
    if not apartment:
        flash("Apartment not found.", "danger")
        return redirect(url_for('apartments.manage_apartments'))

    form = ApartmentForm(obj=apartment)
    categories = apt_service.get_categories()
    form.category_id.choices = [(c.category_id, c.name) for c in categories]

    if form.validate_on_submit():
        success, message, apt = apt_service.update_apartment(
            apartment_id=apartment_id,
            title=form.title.data,
            description=form.description.data,
            price_per_night=form.price_per_night.data,
            category_id=form.category_id.data,
            status=form.status.data,
            bedrooms=form.bedrooms.data,
            bathrooms=form.bathrooms.data,
            capacity=form.capacity.data,
            admin_user_id=current_user.user_id
        )
        if success:
            flash(message, 'success')
            return redirect(url_for('apartments.manage_apartments'))
        else:
            flash(message, 'danger')

    return render_template('edit.html', form=form, apartment=apartment, title=f"Edit {apartment.title} - Admin")


@admin_only
def upload_images(apartment_id):
    apartment = apt_service.get_apartment_by_id(apartment_id)
    if not apartment:
        flash("Apartment not found.", "danger")
        return redirect(url_for('apartments.manage_apartments'))

    form = MultipleImageUploadForm()
    if request.method == 'POST':
        files = request.files.getlist('images')
        if files:
            success, message = apt_service.upload_apartment_images(
                apartment_id=apartment_id,
                image_files=files,
                caption=form.caption.data,
                admin_user_id=current_user.user_id
            )
            flash(message, 'success' if success else 'danger')
            return redirect(url_for('apartments.upload_images', apartment_id=apartment_id))

    return render_template('upload_images.html', form=form, apartment=apartment, title=f"Upload Room Images - {apartment.title}")


def create_booking(apartment_id):
    apartment = apt_service.get_apartment_by_id(apartment_id)
    if not apartment:
        flash("Apartment suite not found.", "danger")
        return redirect(url_for('apartments.list_apartments'))

    form = BookingRequestForm(apartment_id=apartment_id)
    referral_code = request.args.get('ref') or request.args.get('agent_code') or request.args.get('referral_code') or form.referral_code.data

    if request.method == 'GET' and current_user.is_authenticated:
        form.guest_name.data = current_user.full_name
        form.guest_email.data = current_user.email
        form.guest_phone.data = current_user.phone or ''

    if form.validate_on_submit():
        success, message, booking = booking_service.create_booking_request(
            apartment_id=apartment_id,
            check_in_str=form.check_in.data.strftime('%Y-%m-%d'),
            check_out_str=form.check_out.data.strftime('%Y-%m-%d'),
            guest_count=form.guest_count.data,
            guest_name=form.guest_name.data,
            guest_email=form.guest_email.data,
            guest_phone=form.guest_phone.data,
            user_id=current_user.user_id if current_user.is_authenticated else None,
            referral_code=referral_code,
            special_requests=form.special_requests.data,
            source='website'
        )
        if success:
            flash(message, 'success')
            return redirect(url_for('bookings.detail_booking', booking_ref=booking.booking_ref))
        else:
            flash(message, 'danger')

    return render_template('create.html', form=form, apartment=apartment, title=f"Reserve {apartment.title} - The Height Apartment")


def detail_booking(booking_ref):
    booking = booking_service.get_booking_by_ref(booking_ref)
    if not booking:
        flash("Booking record not found.", "warning")
        return redirect(url_for('public.index'))

    return render_template('detail.html', booking=booking, title=f"Booking {booking.booking_ref} - The Height Apartment")


def list_user_bookings():
    if not current_user.is_authenticated:
        flash("Please sign in to view your booking history.", "warning")
        return redirect(url_for('auth.login'))

    bookings = booking_service.get_user_bookings(current_user.user_id)
    return render_template('list.html', bookings=bookings, title="My Bookings - The Height Apartment")


@admin_only
def manage_bookings():
    bookings = booking_service.get_all_bookings()
    return render_template('manage.html', bookings=bookings, title="Booking Management - Admin")


def calendar_view(apartment_id):
    apartment = apt_service.get_apartment_by_id(apartment_id)
    if not apartment:
        return "Apartment not found", 404
    return render_template('availability/calendar.html', apartment=apartment, title=f"Availability Calendar - {apartment.title}")


def availability_events(apartment_id):
    bookings = Booking.query.filter(
        Booking.apartment_id == apartment_id,
        Booking.status.in_(['pending', 'confirmed', 'checked-in'])
    ).all()

    events = []
    for b in bookings:
        color = '#D19828' if b.status == 'pending' else '#198754'
        events.append({
            'id': b.booking_id,
            'title': 'Reserved' if b.status == 'confirmed' else 'Pending Verification',
            'start': b.check_in.strftime('%Y-%m-%d'),
            'end': b.check_out.strftime('%Y-%m-%d'),
            'color': color,
            'allDay': True
        })

    return jsonify(events)


def submit_payment(booking_ref):
    booking = booking_service.get_booking_by_ref(booking_ref)
    if not booking:
        flash("Booking reference invalid.", "danger")
        return redirect(url_for('public.index'))

    form = PaymentProofForm()
    if request.method == 'GET':
        form.amount.data = booking.deposit_required

    if form.validate_on_submit():
        proof_file = form.payment_proof.data
        is_paystack_flow = request.form.get('payment_method') == 'paystack' or proof_file is None
        if is_paystack_flow:
            success, message, payment = payment_service.initialize_paystack_payment(
                booking_ref=booking_ref,
                amount=form.amount.data,
                user_id=current_user.user_id if current_user.is_authenticated else None,
                transaction_ref=form.transaction_ref.data or None,
                email=current_user.email if current_user.is_authenticated else None
            )
            if success and payment and payment.gateway_response:
                gateway_data = json.loads(payment.gateway_response)
                if gateway_data.get('authorization_url'):
                    return render_template(
                        'paystack_redirect.html',
                        booking=booking,
                        authorization_url=gateway_data['authorization_url'],
                        title='Redirecting to Paystack'
                    )
            flash(message, 'success' if success else 'danger')
            return redirect(url_for('bookings.detail_booking', booking_ref=booking_ref))

        success, message, payment = payment_service.submit_bank_transfer_proof(
            booking_ref=booking_ref,
            amount=form.amount.data,
            payment_proof_file=proof_file,
            transaction_ref=form.transaction_ref.data,
            user_id=current_user.user_id if current_user.is_authenticated else None
        )
        if success:
            flash(message, 'success')
            return redirect(url_for('bookings.detail_booking', booking_ref=booking_ref))
        else:
            flash(message, 'danger')

    return render_template('payment_form.html', form=form, booking=booking, title=f"Submit Deposit - {booking.booking_ref}")


def paystack_callback(reference):
    payment = payment_service.payment_repo.find_by_transaction_ref(reference)
    if not payment:
        flash('Payment reference was not found.', 'danger')
        return redirect(url_for('public.index'))

    success, message, receipt = payment_service.verify_paystack_payment(reference)
    if success:
        flash("Your Paystack payment was verified and your booking is now confirmed.", 'success')
    else:
        flash(message or 'Paystack verification failed. Please try again or contact support.', 'danger')

    if payment and payment.booking:
        return redirect(url_for('bookings.detail_booking', booking_ref=payment.booking.booking_ref))
    return redirect(url_for('public.index'))


def paystack_webhook():
    payload = request.get_data()
    signature = request.headers.get('x-paystack-signature')
    if not signature:
        return jsonify({'status': 'error', 'message': 'Missing signature'}), 400

    success, message, receipt = payment_service.process_paystack_webhook(payload, signature)
    if success:
        return jsonify({'status': 'success', 'message': 'Webhook processed'}), 200
    return jsonify({'status': 'error', 'message': message or 'Webhook processing failed'}), 400


@admin_only
def manage_payments():
    pending_payments = payment_service.get_pending_payments()
    return render_template('confirmation.html', payments=pending_payments, title="Payment Verifications - Admin")


@admin_only
def verify_payment(payment_id):
    success, message, receipt = payment_service.verify_payment_and_generate_receipt(
        payment_id=payment_id,
        admin_user_id=current_user.user_id
    )
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('payments.manage_payments'))


def corporate_index():
    return render_template('corporate_index.html', title="Corporate & Extended Stays - The Height Premium Apartment")


def request_quote():
    form = CorporateEnquiryForm()
    if form.validate_on_submit():
        success, message, enquiry = corp_service.submit_corporate_enquiry(
            company_name=form.company_name.data,
            contact_person=form.contact_person.data,
            email=form.email.data,
            phone=form.phone.data,
            check_in_str=form.check_in.data.strftime('%Y-%m-%d'),
            check_out_str=form.check_out.data.strftime('%Y-%m-%d'),
            guest_count=form.guest_count.data,
            suite_count=form.suite_count.data,
            budget_range=form.budget_range.data,
            special_requests=form.special_requests.data
        )
        if success:
            flash(message, 'success')
            return redirect(url_for('corporate.corporate_index'))
        else:
            flash(message, 'danger')

    return render_template('request_quote.html', form=form, title="Request a Corporate Quote - The Height Premium Apartment")


@admin_only
def manage_enquiries():
    enquiries = corp_service.get_all_enquiries()
    return render_template('corporate_list.html', enquiries=enquiries, title="Corporate Enquiries - Admin")


@admin_only
def create_quote(enquiry_id):
    enquiry = corp_service.enquiry_repo.get_by_id(enquiry_id)
    if not enquiry:
        flash("Enquiry not found.", "danger")
        return redirect(url_for('corporate.manage_enquiries'))

    form = QuoteGeneratorForm()
    if form.validate_on_submit():
        success, message, quote = corp_service.create_quotation(
            enquiry_id=enquiry_id,
            amount=form.amount.data,
            discount=form.discount.data,
            room_type=form.room_type.data,
            valid_until_str=form.valid_until.data.strftime('%Y-%m-%d'),
            terms=form.terms.data,
            admin_user_id=current_user.user_id
        )
        if success:
            flash(message, 'success')
            return redirect(url_for('corporate.view_quote', quote_number=quote.quote_number))
        else:
            flash(message, 'danger')

    return render_template('create_quote.html', form=form, enquiry=enquiry, title=f"Create Quote for {enquiry.company_name}")


def view_quote(quote_number):
    quote = corp_service.get_quote_by_number(quote_number)
    if not quote:
        flash("Quotation not found.", "warning")
        return redirect(url_for('corporate.corporate_index'))

    return render_template('quote_detail.html', quote=quote, title=f"Quotation {quote.quote_number} - The Height Premium Apartment")


def view_receipt(booking_ref):
    booking = booking_service.get_booking_by_ref(booking_ref)
    if not booking or not booking.receipt:
        flash("Receipt not yet generated for this booking. Payment verification pending.", "warning")
        return redirect(url_for('bookings.detail_booking', booking_ref=booking_ref))

    return render_template('receipt_template.html', booking=booking, receipt=booking.receipt, title=f"Receipt {booking.receipt.receipt_number}")


def download_pdf(booking_ref):
    booking = booking_service.get_booking_by_ref(booking_ref)
    if not booking or not booking.receipt or not booking.receipt.pdf_path:
        flash("Receipt PDF not found.", "danger")
        return redirect(url_for('public.index'))

    rel_path = booking.receipt.pdf_path.replace('/static/uploads/', '')
    abs_pdf_path = os.path.join(current_app.config['UPLOAD_FOLDER'], rel_path)

    if os.path.exists(abs_pdf_path):
        return send_file(abs_pdf_path, as_attachment=True, download_name=f"{booking.receipt.receipt_number}.pdf")
    else:
        flash("File path error on server.", "danger")
        return redirect(url_for('public.index'))


@admin_only
def index_reports():
    return render_template('reports.html', title="Financial & Operational Reports - Admin")


@admin_only
def export_bookings_csv():
    csv_data = ReportService.generate_bookings_csv()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=the_height_bookings_report.csv"}
    )


def register_agent():
    if current_user.is_authenticated and current_user.is_agent:
        return redirect(url_for('agents.dashboard'))

    form = AgentRegistrationForm()
    if form.validate_on_submit():
        success, message, agent = agent_service.register_agent(
            full_name=form.full_name.data,
            email=form.email.data,
            password=form.password.data,
            phone=form.phone.data,
            bank_name=form.bank_name.data,
            account_number=form.account_number.data,
            account_holder_name=form.account_holder_name.data
        )
        if success:
            flash(message, 'success')
            return redirect(url_for('auth.login'))
        else:
            flash(message, 'danger')

    return render_template('agent_registration.html', form=form, title="Partner Agent Registration - The Height Apartment")


@agent_only
def dashboard_agent():
    agent = current_user.agent_profile
    commissions = agent_service.comm_repo.get_commissions_by_agent(agent.agent_id) if agent else []
    return render_template('agent_dashboard.html', agent=agent, commissions=commissions, title="Agent Dashboard - The Height Apartment")


@agent_only
def profile_agent():
    agent = current_user.agent_profile
    return render_template('agent_profile.html', agent=agent, title="Agent Profile - The Height Apartment")


@agent_only
def commission_history():
    agent = current_user.agent_profile
    commissions = agent_service.comm_repo.get_commissions_by_agent(agent.agent_id) if agent else []
    return render_template('commission_history.html', agent=agent, commissions=commissions, title="Commission Ledger - Agent")


@agent_only
def agent_bookings():
    agent = current_user.agent_profile
    commissions = agent_service.comm_repo.get_commissions_by_agent(agent.agent_id) if agent else []
    return render_template('agent_bookings.html', agent=agent, commissions=commissions, title="My Referred Bookings")


def write_review(booking_ref):
    booking = booking_service.get_booking_by_ref(booking_ref)
    if not booking:
        flash("Invalid booking reference.", "danger")
        return redirect(url_for('public.index'))

    if booking.status not in ['checked-out', 'completed']:
        flash("Review Policy: Reviews can only be submitted after completing your verified stay.", "warning")
        return redirect(url_for('bookings.detail_booking', booking_ref=booking_ref))

    form = ReviewForm()
    if form.validate_on_submit():
        success, message, review = review_service.submit_verified_review(
            booking_ref=booking_ref,
            rating=form.rating.data,
            title=form.title.data,
            comment=form.comment.data,
            user_id=current_user.user_id if current_user.is_authenticated else None
        )
        if success:
            flash(message, 'success')
            return redirect(url_for('reviews.view_suite_reviews', apartment_id=booking.apartment_id))
        else:
            flash(message, 'danger')

    return render_template('write_review.html', form=form, booking=booking, title=f"Write Review - {booking.apartment.title}")


def view_suite_reviews(apartment_id):
    apartment = apt_service.get_apartment_by_id(apartment_id)
    if not apartment:
        flash("Apartment suite not found.", "warning")
        return redirect(url_for('apartments.list_apartments'))

    reviews = review_service.get_apartment_reviews(apartment_id)
    return render_template('view_reviews.html', apartment=apartment, reviews=reviews, title=f"Reviews for {apartment.title}")


@admin_only
def dashboard_admin():
    metrics = DashboardService.get_admin_metrics()
    return render_template('admin_dashboard.html', metrics=metrics, title="Admin Control Center - The Height Apartment")


@superadmin_only
def dashboard_superadmin():
    metrics = DashboardService.get_superadmin_metrics()
    return render_template('superadmin_dashboard.html', metrics=metrics, title="SuperAdmin Control Center - The Height Apartment")


@superadmin_only
def audit_logs():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).all()
    return render_template('audit_logs.html', logs=logs, title="System Audit Logs - SuperAdmin")


@superadmin_only
def user_management():
    users = User.query.order_by(User.created_at.desc()).all()
    roles = Role.query.all()
    return render_template('user_management.html', users=users, roles=roles, title="User & Role Governance - SuperAdmin")
