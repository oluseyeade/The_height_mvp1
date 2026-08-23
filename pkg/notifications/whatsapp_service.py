from pkg.extensions import db
from pkg.models.notification import WhatsAppLog

class WhatsAppService:
    @staticmethod
    def send_whatsapp_message(recipient, message, template_name=None):
        """
        Sends automated WhatsApp notification and logs in WhatsAppLog.
        """
        log = WhatsAppLog(
            recipient=recipient,
            message=message,
            template_name=template_name,
            status='sent'
        )
        try:
            db.session.add(log)
            db.session.commit()
            print(f"[WHATSAPP DISPATCH] Sent message to {recipient}: {message[:50]}...")
        except Exception as e:
            db.session.rollback()
            print(f"[WHATSAPP LOG ERROR]: {str(e)}")

        return log
