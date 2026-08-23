from flask import render_template, flash, redirect, url_for
from flask_login import current_user
from app.models import Receipt

def init_receipt_routes(app):
    @app.route('/receipts/<receipt_number>', endpoint='receipts.view_receipt')
    def view_receipt(receipt_number):
        receipt = Receipt.query.filter_by(receipt_number=receipt_number).first()
        if not receipt:
            flash('Receipt not found.', 'danger')
            return redirect(url_for('public.index'))

        # Security Ownership Authorization Guard for Logged-In Customers
        if current_user.is_authenticated and not (getattr(current_user, 'is_admin', False) or getattr(current_user, 'is_superadmin', False)):
            b = receipt.payment.booking if receipt.payment else None
            if b and b.user_id and b.user_id != current_user.user_id and (b.guest_email and b.guest_email != current_user.email):
                flash('Access denied: You do not have permission to view this receipt.', 'danger')
                return redirect(url_for('auth.profile'))

        return render_template('receipts/receipt_template.html', receipt=receipt)
