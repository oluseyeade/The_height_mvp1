import json
import os
from datetime import datetime, timezone
from pkg.repositories.payment_repository import PaymentRepository, ReceiptRepository
from pkg.repositories.booking_repository import BookingRepository
from pkg.models.payment import Payment
from pkg.models.receipt import Receipt
from pkg.services.audit_service import AuditService
from pkg.utils.file_upload import save_uploaded_image
from pkg.receipts.pdf import create_branded_receipt_pdf
from pkg.payments.gateways import PaystackGateway
from pkg.extensions import db
from flask import current_app, request
from sqlalchemy import and_

class PaymentService:
    def __init__(self):
        self.payment_repo = PaymentRepository()
        self.receipt_repo = ReceiptRepository()
        self.booking_repo = BookingRepository()
        self.paystack_gateway = PaystackGateway()

    def _build_paystack_callback_url(self, reference):
        configured_callback = current_app.config.get('PAYSTACK_CALLBACK_URL') or os.getenv('PAYSTACK_CALLBACK_URL')
        if configured_callback:
            callback_url = configured_callback.strip().rstrip('/')
            if callback_url.endswith('/payments/paystack/callback'):
                return f"{callback_url}/{reference}"
            if '/payments/paystack/callback' in callback_url:
                return f"{callback_url}/{reference}"
            return f"{callback_url}/payments/paystack/callback/{reference}"

        if request:
            try:
                return request.host_url.rstrip('/') + f'/payments/paystack/callback/{reference}'
            except RuntimeError:
                return None

        return None

    def _get_gateway_error_message(self, gateway_data):
        if isinstance(gateway_data, str):
            return gateway_data
        if isinstance(gateway_data, dict):
            if gateway_data.get('message'):
                return gateway_data.get('message')
            data = gateway_data.get('data')
            if isinstance(data, dict):
                if data.get('message'):
                    return data.get('message')
        return 'Paystack reported an unsuccessful transaction.'

    def _is_paystack_success(self, gateway_data):
        if not isinstance(gateway_data, dict):
            return False

        if gateway_data.get('status') == 'success':
            return True

        data = gateway_data.get('data')
        if isinstance(data, dict):
            return str(data.get('status', '')).lower() == 'success'

        return False

    def _log_verification_attempt(self, payment, outcome, gateway_data=None, source='callback'):
        details = {
            'payment_id': payment.payment_id,
            'reference': payment.transaction_ref,
            'outcome': outcome,
            'source': source,
            'gateway_data': gateway_data,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        payment.notes = json.dumps(details)
        self.payment_repo.commit()

    def _validate_gateway_payload(self, payment, gateway_data, expected_amount, expected_currency='NGN'):
        if not isinstance(gateway_data, dict):
            return False, 'Paystack returned an invalid verification payload.'

        if gateway_data.get('status') != 'success' and str(gateway_data.get('status', '')).lower() != 'success':
            return False, self._get_gateway_error_message(gateway_data)

        if gateway_data.get('reference') and payment.transaction_ref and str(gateway_data.get('reference')) != str(payment.transaction_ref):
            return False, 'Transaction reference mismatch.'

        amount_value = gateway_data.get('amount')
        if amount_value is None:
            amount_value = gateway_data.get('data', {}).get('amount') if isinstance(gateway_data.get('data'), dict) else None
        if amount_value is None:
            return False, 'Paystack verification response did not include an amount.'

        if int(float(amount_value)) != int(float(expected_amount) * 100):
            return False, 'Paystack amount does not match the expected booking amount.'

        currency = gateway_data.get('currency') or (gateway_data.get('data', {}).get('currency') if isinstance(gateway_data.get('data'), dict) else None)
        if currency and str(currency).upper() != str(expected_currency).upper():
            return False, 'Paystack currency does not match the configured currency.'

        return True, None

    def _finalize_verified_payment(self, payment, admin_user_id=None):
        if not payment:
            return False, "Payment record not found.", None

        if payment.status == 'verified':
            receipt = self.receipt_repo.find_by_booking_id(payment.booking_id)
            return True, "Payment is already verified.", receipt

        payment.status = 'verified'
        payment.verified_by = admin_user_id
        payment.verified_at = datetime.now(timezone.utc)

        booking = payment.booking
        booking.status = 'confirmed'
        self.payment_repo.commit()

        receipt = self.receipt_repo.find_by_booking_id(payment.booking_id)
        if receipt:
            return True, f"Payment verified successfully! Receipt {receipt.receipt_number} already exists.", receipt

        receipt_number = Receipt.generate_number()
        pdf_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'receipts', 'pdf')
        pdf_filename = f"{receipt_number}.pdf"
        output_pdf_path = os.path.join(pdf_dir, pdf_filename)
        rel_pdf_path = f"/static/uploads/receipts/pdf/{pdf_filename}"

        _, rel_qr_path = create_branded_receipt_pdf(
            receipt_number=receipt_number,
            booking=booking,
            payment=payment,
            output_pdf_path=output_pdf_path
        )

        receipt = Receipt(
            payment_id=payment.payment_id,
            booking_id=booking.booking_id,
            receipt_number=receipt_number,
            pdf_path=rel_pdf_path,
            qr_code_path=rel_qr_path
        )
        self.receipt_repo.add(receipt)
        self.receipt_repo.commit()

        if admin_user_id:
            AuditService.log_admin_action(
                admin_id=admin_user_id,
                target_user_id=payment.user_id,
                action_type='PAYMENT_VERIFIED',
                previous_status='pending',
                new_status='verified',
                reason=f"Verified ₦{payment.amount:,.2f} for booking {booking.booking_ref}. Receipt {receipt_number} issued."
            )
        else:
            AuditService.log_activity(
                user_id=payment.user_id or booking.user_id,
                activity_type='PAYMENT_VERIFIED',
                description=f"Paystack payment of ₦{payment.amount:,.2f} verified for booking {booking.booking_ref}.",
                module='Payment',
                action='verify'
            )

        return True, f"Payment verified successfully! Receipt {receipt_number} generated.", receipt

    def process_paystack_callback(self, reference, gateway_data=None, source='callback', expected_amount=None, expected_currency='NGN'):
        payment = self.payment_repo.find_by_transaction_ref(reference)
        if not payment:
            return False, "Payment record not found for the provided reference.", None

        if payment.status == 'verified':
            receipt = self.receipt_repo.find_by_booking_id(payment.booking_id)
            return True, "Payment is already verified.", receipt

        if gateway_data is None:
            success, gateway_data = self.paystack_gateway.verify_transaction(reference)
            if not success:
                payment.status = 'rejected'
                self._log_verification_attempt(payment, 'failed', gateway_data, source=source)
                return False, self._get_gateway_error_message(gateway_data), None

        is_valid, error_message = self._validate_gateway_payload(payment, gateway_data, expected_amount or payment.amount, expected_currency)
        if not is_valid:
            payment.status = 'rejected'
            self._log_verification_attempt(payment, 'failed', gateway_data, source=source)
            return False, error_message, None

        if payment.status == 'rejected' and payment.notes:
            self._log_verification_attempt(payment, 'duplicate', gateway_data, source=source)
            return False, 'Payment has already been processed with a failed verification result.', None

        self._log_verification_attempt(payment, 'verified', gateway_data, source=source)
        return self._finalize_verified_payment(payment, admin_user_id=None)

    def process_paystack_webhook(self, payload, signature, expected_amount=None, expected_currency='NGN'):
        if not self.paystack_gateway.verify_webhook_signature(payload, signature):
            return False, 'Invalid webhook signature.', None

        try:
            event = json.loads(payload.decode('utf-8') if isinstance(payload, bytes) else payload)
        except (TypeError, ValueError):
            return False, 'Invalid webhook payload.', None

        event_data = event.get('data') or {}
        reference = event_data.get('reference')
        if not reference:
            return False, 'Webhook missing transaction reference.', None

        gateway_data = event_data
        return self.process_paystack_callback(reference, gateway_data=gateway_data, source='webhook', expected_amount=expected_amount, expected_currency=expected_currency)

    def initialize_paystack_payment(self, booking_ref, amount, user_id=None, transaction_ref=None, email=None):
        booking = self.booking_repo.find_by_ref(booking_ref)
        if not booking:
            return False, "Booking reference not found.", None

        existing_payment = self.payment_repo.find_by_booking_id(booking.booking_id)
        pending_payment = next((p for p in existing_payment if p.status == 'pending' and p.payment_method == 'paystack'), None)
        if pending_payment:
            return True, "A Paystack payment is already in progress for this booking.", pending_payment

        reference = transaction_ref or f"THA-PS-{booking.booking_ref}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        email_address = email or booking.guest_email or (booking.user.email if booking.user else None) or 'guest@example.com'
        amount_kobo = int(float(amount) * 100)

        callback_url = self._build_paystack_callback_url(reference)
        if callback_url and '://' not in callback_url:
            callback_url = f'https://{callback_url}'

        success, authorization_url, returned_reference = self.paystack_gateway.initialize_transaction(
            email=email_address,
            amount_kobo=amount_kobo,
            reference=reference,
            callback_url=callback_url
        )

        if not success:
            return False, authorization_url or 'Paystack initialization failed.', None

        payment = Payment(
            booking_id=booking.booking_id,
            user_id=user_id or booking.user_id,
            amount=float(amount),
            payment_method='paystack',
            transaction_ref=returned_reference or reference,
            status='pending'
        )
        self.payment_repo.add(payment)
        self.payment_repo.commit()

        payment.gateway_response = json.dumps({
            'authorization_url': authorization_url,
            'reference': returned_reference or reference,
            'callback_url': callback_url
        })
        self.payment_repo.commit()

        AuditService.log_activity(
            user_id=user_id or booking.user_id,
            activity_type='PAYSTACK_INITIATED',
            description=f"Paystack checkout initialized for booking {booking.booking_ref}.",
            module='Payment',
            action='initialize'
        )

        return True, "Paystack checkout initialized successfully. Complete the payment to confirm your booking.", payment

    def verify_paystack_payment(self, reference):
        return self.process_paystack_callback(reference, gateway_data=None, source='callback')

    def submit_bank_transfer_proof(self, booking_ref, amount, payment_proof_file, transaction_ref=None, user_id=None):
        booking = self.booking_repo.find_by_ref(booking_ref)
        if not booking:
            return False, "Booking reference not found.", None

        rel_path = save_uploaded_image(payment_proof_file, folder_name='payment_proofs')
        if not rel_path:
            return False, "Payment proof file upload failed.", None

        payment = Payment(
            booking_id=booking.booking_id,
            user_id=user_id or booking.user_id,
            amount=float(amount),
            payment_method='bank_transfer',
            transaction_ref=transaction_ref or f"BT-{booking.booking_ref}",
            payment_proof=rel_path,
            status='pending'
        )

        self.payment_repo.add(payment)
        self.payment_repo.commit()

        AuditService.log_activity(
            user_id=user_id or booking.user_id,
            activity_type='PAYMENT_PROOF_SUBMITTED',
            description=f"Bank transfer payment proof of ₦{amount:,.2f} uploaded for booking {booking_ref}.",
            module='Payment',
            action='submit_proof'
        )

        return True, "Payment proof uploaded successfully. Awaiting Admin verification.", payment

    def verify_payment_and_generate_receipt(self, payment_id, admin_user_id):
        payment = self.payment_repo.get_by_id(payment_id)
        if not payment:
            return False, "Payment record not found.", None

        if payment.status == 'verified':
            return False, "Payment has already been verified.", None

        payment.status = 'verified'
        payment.verified_by = admin_user_id
        payment.verified_at = datetime.now(timezone.utc)

        return self._finalize_verified_payment(payment, admin_user_id=admin_user_id)

    def get_pending_payments(self):
        return self.payment_repo.get_pending_payments()
