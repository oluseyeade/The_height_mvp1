import json
from datetime import datetime
from pkg.repositories.corporate_repository import CorporateRepository, CorporateQuoteRepository
from pkg.models.corporate import CorporateEnquiry, CorporateQuote
from pkg.services.audit_service import AuditService
from pkg.extensions import db

class CorporateService:
    def __init__(self):
        self.enquiry_repo = CorporateRepository()
        self.quote_repo = CorporateQuoteRepository()

    def submit_corporate_enquiry(self, company_name, contact_person, email, phone,
                                check_in_str, check_out_str, guest_count=1, suite_count=1,
                                budget_range=None, special_requests=None):
        try:
            check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
            check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()
        except ValueError:
            return False, "Invalid check-in or check-out date format.", None

        if check_in >= check_out:
            return False, "Check-out date must be after check-in date.", None

        length_of_stay = (check_out - check_in).days

        enquiry = CorporateEnquiry(
            company_name=company_name.strip(),
            contact_person=contact_person.strip(),
            email=email.lower().strip(),
            phone=phone.strip(),
            check_in=check_in,
            check_out=check_out,
            guest_count=int(guest_count),
            suite_count=int(suite_count),
            length_of_stay=length_of_stay,
            budget_range=budget_range.strip() if budget_range else None,
            special_requests=special_requests.strip() if special_requests else None,
            status='new'
        )

        self.enquiry_repo.add(enquiry)
        self.enquiry_repo.commit()

        AuditService.log_activity(
            user_id=None,
            activity_type='CORPORATE_ENQUIRY',
            description=f"Corporate enquiry submitted by {company_name} ({contact_person}).",
            module='Corporate',
            action='submit_enquiry'
        )

        return True, "Corporate enquiry submitted successfully. Our B2B Account Manager will respond within 2 hours.", enquiry

    def create_quotation(self, enquiry_id, amount, discount, room_type, valid_until_str, inclusions=None, terms=None, admin_user_id=None):
        enquiry = self.enquiry_repo.get_by_id(enquiry_id)
        if not enquiry:
            return False, "Corporate enquiry not found.", None

        try:
            valid_until = datetime.strptime(valid_until_str, '%Y-%m-%d').date()
        except ValueError:
            return False, "Invalid valid-until date format.", None

        amount_val = float(amount)
        discount_val = float(discount or 0.0)
        final_amount = max(0.0, amount_val - discount_val)

        quote = CorporateQuote(
            enquiry_id=enquiry_id,
            created_by=admin_user_id,
            quote_number=CorporateQuote.generate_number(),
            amount=amount_val,
            discount=discount_val,
            final_amount=final_amount,
            room_type=room_type.strip(),
            inclusions_json=json.dumps(inclusions) if inclusions else None,
            terms=terms.strip() if terms else "Standard B2B Terms & Conditions apply.",
            valid_until=valid_until,
            status='sent'
        )

        enquiry.status = 'quoted'
        self.quote_repo.add(quote)
        self.quote_repo.commit()

        if admin_user_id:
            AuditService.log_admin_action(
                admin_id=admin_user_id,
                target_user_id=None,
                action_type='CREATE_CORPORATE_QUOTE',
                previous_status=enquiry.status,
                new_status='quoted',
                reason=f"Issued B2B quotation {quote.quote_number} of ₦{final_amount:,.2f} for {enquiry.company_name}"
            )

        return True, f"Quotation {quote.quote_number} generated and sent.", quote

    def get_quote_by_number(self, quote_number):
        return self.quote_repo.find_by_quote_number(quote_number)

    def get_all_enquiries(self):
        return self.enquiry_repo.get_all_enquiries()
