from flask import render_template, current_app
from flask_mail import Message
from pkg.extensions import mail, db
from pkg.models.notification import EmailLog

class EmailService:
    @staticmethod
    def send_transactional_email(recipient, subject, body, template_name=None):
        """
        Sends transactional email and records entry in EmailLog.
        """
        log = EmailLog(
            recipient=recipient,
            subject=subject,
            body=body,
            template_name=template_name,
            status='sent'
        )

        try:
            msg = Message(
                subject=subject,
                recipients=[recipient],
                body=body,
                sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@theheightapartment.com')
            )
            mail.send(msg)
            log.status = 'sent'
        except Exception as e:
            log.status = 'failed'
            log.error_message = str(e)
            print(f"[EMAIL SERVICE ERROR]: {str(e)}")

        try:
            db.session.add(log)
            db.session.commit()
        except Exception:
            db.session.rollback()

        return log
