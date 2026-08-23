from pkg.repositories.base_repository import BaseRepository
from pkg.models.payment import Payment
from pkg.models.receipt import Receipt

class PaymentRepository(BaseRepository):
    def __init__(self):
        super().__init__(Payment)

    def find_by_booking_id(self, booking_id):
        return Payment.query.filter_by(booking_id=booking_id).all()

    def find_by_transaction_ref(self, ref):
        return Payment.query.filter_by(transaction_ref=ref).first()

    def get_pending_payments(self):
        return Payment.query.filter_by(status='pending').order_by(Payment.created_at.desc()).all()


class ReceiptRepository(BaseRepository):
    def __init__(self):
        super().__init__(Receipt)

    def find_by_booking_id(self, booking_id):
        return Receipt.query.filter_by(booking_id=booking_id).first()

    def find_by_number(self, receipt_number):
        return Receipt.query.filter_by(receipt_number=receipt_number).first()
