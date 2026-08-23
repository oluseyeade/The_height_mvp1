import hmac
import hashlib
from flask import request, jsonify, redirect, url_for, flash, current_app
from flask_login import current_user
from app.models import Payment
from app.services import PaymentService

payment_service = PaymentService()

def init_payment_routes(app):
    @app.route('/payments/paystack/initialize/<booking_ref>', methods=['GET', 'POST'], endpoint='payments.paystack_initialize')
    def paystack_initialize(booking_ref):
        user_id = current_user.user_id if current_user.is_authenticated else None
        res, msg = payment_service.initialize_paystack_payment(booking_ref, user_id=user_id)
        
        if not res or not res.get('success'):
            if request.is_json or request.headers.get('Accept') == 'application/json':
                return jsonify({"success": False, "message": msg}), 400
            flash(msg, 'danger')
            return redirect(url_for('bookings.detail', booking_ref=booking_ref))

        if request.is_json or request.headers.get('Accept') == 'application/json':
            return jsonify(res), 200

        return redirect(res.get('authorization_url'))

    @app.route('/payments/paystack/callback', methods=['GET', 'POST'], endpoint='payments.paystack_callback')
    def paystack_callback():
        reference = request.args.get('reference') or request.args.get('trxref') or request.form.get('reference')
        if not reference:
            flash('No payment reference received from Paystack callback.', 'danger')
            return redirect(url_for('apartments.list_apartments'))

        success, booking, msg = payment_service.verify_paystack_payment(reference)
        if success and booking:
            flash('Payment verified successfully! Your reservation is active and confirmed.', 'success')
            return redirect(url_for('bookings.success', booking_ref=booking.booking_ref))
        else:
            b_ref = booking.booking_ref if booking else ''
            flash(msg or 'Payment was not successful or was cancelled. You may retry payment.', 'warning')
            if b_ref:
                return redirect(url_for('bookings.detail', booking_ref=b_ref))
            return redirect(url_for('apartments.list_apartments'))

    @app.route('/payments/webhook/paystack', methods=['POST'], endpoint='payments.paystack_webhook')
    def paystack_webhook():
        paystack_signature = request.headers.get('X-Paystack-Signature')
        secret_key = current_app.config.get('PAYSTACK_WEBHOOK_SECRET') or current_app.config.get('PAYSTACK_SECRET_KEY', '')

        # HMAC SHA512 Signature Verification
        if paystack_signature and secret_key:
            computed_hmac = hmac.new(
                secret_key.encode('utf-8'),
                request.get_data(),
                hashlib.sha512
            ).hexdigest()

            if not hmac.compare_digest(computed_hmac.lower(), paystack_signature.lower()):
                current_app.logger.warning("Invalid Paystack webhook signature received.")
                return jsonify({'status': 'error', 'message': 'Invalid Paystack signature'}), 400

        data = request.get_json(silent=True) or {}
        event = data.get('event')

        if event == 'charge.success':
            event_data = data.get('data', {})
            tx_ref = event_data.get('reference')
            if tx_ref:
                payment_service.verify_paystack_payment(tx_ref)

        return jsonify({'status': 'success', 'message': 'Webhook processed successfully'}), 200

    @app.route('/payments/verify/<transaction_ref>', endpoint='payments.verify_transaction')
    def verify_transaction(transaction_ref):
        success, booking, msg = payment_service.verify_paystack_payment(transaction_ref)
        if success and booking:
            flash('Payment verified successfully!', 'success')
            return redirect(url_for('bookings.success', booking_ref=booking.booking_ref))

        flash('Payment is currently pending or verification failed.', 'warning')
        return redirect(url_for('bookings.detail', booking_ref=booking.booking_ref if booking else ''))
