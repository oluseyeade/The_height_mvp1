from datetime import datetime
from flask import render_template, request, flash, redirect, url_for
from app.extensions import db
from app.models import CorporateEnquiry

def init_corporate_routes(app):
    @app.route('/corporate/', endpoint='corporate.corporate_stays')
    def corporate_stays():
        return render_template('corporate/corporate_stays.html')

    @app.route('/corporate/enquire', methods=['POST'], endpoint='corporate.submit_enquiry')
    def submit_enquiry():
        try:
            company_name = request.form.get('company_name')
            contact_person = request.form.get('contact_person')
            email = request.form.get('email')
            phone = request.form.get('phone')
            check_in_str = request.form.get('check_in')
            check_out_str = request.form.get('check_out')
            guest_count = int(request.form.get('guest_count', 1))
            suite_count = int(request.form.get('suite_count', 1))
            special_requests = request.form.get('special_requests')

            check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
            check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()

            enquiry = CorporateEnquiry(
                company_name=company_name,
                contact_person=contact_person,
                email=email,
                phone=phone,
                check_in=check_in,
                check_out=check_out,
                guest_count=guest_count,
                suite_count=suite_count,
                special_requests=special_requests,
                status='new'
            )
            db.session.add(enquiry)
            db.session.commit()

            # Trigger SuperAdmin Notification for Corporate Request
            from app.services import NotificationService
            NotificationService.create_notification(
                notification_type='CORPORATE_REQUEST_SUBMITTED',
                portal='CORPORATE',
                title='New Corporate Booking Request',
                message=f"New corporate booking request submitted by '{company_name}' ({contact_person}). Review & quotation required.",
                priority='HIGH',
                requires_action=True,
                related_type='CorporateEnquiry',
                related_id=enquiry.enquiry_id,
                action_url='/admin/corporate'
            )

            flash(f'Corporate enquiry received for {company_name}! Our Corporate Account Manager will send a quote shortly.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error submitting enquiry: {str(e)}', 'danger')

        return redirect(url_for('corporate.corporate_stays'))
