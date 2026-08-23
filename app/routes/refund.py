from flask import request, flash, redirect, url_for
from flask_login import current_user
from app.decorators import superadmin_only
from app.models import Booking
from app.services import RefundService

refund_service = RefundService()

def init_refund_routes(app):
    @app.route('/admin/refunds/process', methods=['POST'], endpoint='refunds.process')
    @superadmin_only
    def process_refund():
        booking_id = request.form.get('booking_id')
        refund_type = request.form.get('refund_type', 'full')  # full, partial, withheld
        amount = float(request.form.get('refund_amount', 50000.00))
        reason = request.form.get('refund_reason', '').strip()
        notes = request.form.get('notes', '').strip()

        if not booking_id or not reason:
            flash('Booking ID and Reason are required for processing a refund.', 'danger')
            return redirect(url_for('superadmin_panel.dashboard'))

        refund, msg = refund_service.create_refund_request(
            booking_id=int(booking_id),
            admin_user_id=current_user.user_id,
            refund_type=refund_type,
            amount=amount,
            reason=reason,
            notes=notes
        )

        if refund:
            flash(msg, 'success')
        else:
            flash(msg, 'danger')

        return redirect(url_for('superadmin_panel.dashboard'))
