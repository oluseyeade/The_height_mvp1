from pkg.repositories.base_repository import BaseRepository
from pkg.models.corporate import CorporateEnquiry, CorporateQuote

class CorporateRepository(BaseRepository):
    def __init__(self):
        super().__init__(CorporateEnquiry)

    def get_all_enquiries(self):
        return CorporateEnquiry.query.order_by(CorporateEnquiry.created_at.desc()).all()

    def get_new_enquiries(self):
        return CorporateEnquiry.query.filter_by(status='new').order_by(CorporateEnquiry.created_at.desc()).all()


class CorporateQuoteRepository(BaseRepository):
    def __init__(self):
        super().__init__(CorporateQuote)

    def find_by_quote_number(self, quote_number):
        return CorporateQuote.query.filter_by(quote_number=quote_number.upper().strip()).first()
