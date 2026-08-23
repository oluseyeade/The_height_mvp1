from pkg.notifications.email_service import EmailService
from pkg.notifications.whatsapp_service import WhatsAppService

# Celery async worker task proxies
def async_send_booking_received_notification(recipient_email, recipient_phone, booking_ref, apartment_title):
    subject = f"Booking Request Received - {booking_ref}"
    body = f"Hello, your reservation request for {apartment_title} (Ref: {booking_ref}) has been received. Please pay the ₦50,000 deposit to secure your stay."
    
    EmailService.send_transactional_email(recipient_email, subject, body, 'booking_received')
    if recipient_phone:
        WhatsAppService.send_whatsapp_message(recipient_phone, f"The Height Apartment: Reservation {booking_ref} received. Deposit instructions sent.", 'booking_received')

def async_send_payment_confirmation(recipient_email, recipient_phone, booking_ref, receipt_number):
    subject = f"Payment Confirmed & Official Receipt - {receipt_number}"
    body = f"Thank you! Your payment for reservation {booking_ref} has been verified. Official Receipt #: {receipt_number}."
    
    EmailService.send_transactional_email(recipient_email, subject, body, 'payment_confirmation')
    if recipient_phone:
        WhatsAppService.send_whatsapp_message(recipient_phone, f"The Height Apartment: Payment confirmed for {booking_ref}. Receipt {receipt_number} issued.", 'payment_confirmation')

def async_send_review_invitation(recipient_email, recipient_phone, booking_ref, apartment_title):
    subject = f"How was your stay at {apartment_title}?"
    body = f"Thank you for staying at The Height Apartment! As a verified guest for booking {booking_ref}, we invite you to leave a review."
    
    EmailService.send_transactional_email(recipient_email, subject, body, 'review_invitation')
    if recipient_phone:
        WhatsAppService.send_whatsapp_message(recipient_phone, f"The Height Apartment: Thank you for your stay! Please review your stay at {apartment_title}.", 'review_invitation')
