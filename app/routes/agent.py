import threading
from flask import render_template, request, flash, redirect, url_for, jsonify, send_file, current_app
from flask_login import current_user, login_user
from flask_mail import Message
from app.extensions import db, mail
from app.models import Agent, User
from app.decorators import agent_only
from app.services import UserService
from app.utils import generate_agent_qrcode

user_service = UserService()

def _send_async_agent_email(app_obj, email_msg):
    with app_obj.app_context():
        try:
            mail.send(email_msg)
        except Exception as e:
            app_obj.logger.warning(f"Async agent welcome email skipped: {str(e)}")

def init_agent_routes(app):
    @app.route('/agents/', endpoint='agents.agent_portal')
    @app.route('/agents/registered', endpoint='agents.agent_portal_registered')
    def agent_portal():
        show_success_modal = request.args.get('registered') == '1' or request.path.endswith('/registered')
        agent_name = request.args.get('agent_name', '')
        agent_code = request.args.get('agent_code', '')
        return render_template(
            'agents/agent_portal.html',
            show_success_modal=show_success_modal,
            agent_name=agent_name,
            agent_code=agent_code
        )

    @app.route('/agents/register', methods=['POST'], endpoint='agents.register_agent')
    def register_agent():
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        bank_name = request.form.get('bank_name')
        account_number = request.form.get('account_number')

        user, msg = user_service.register_user(
            full_name=full_name,
            email=email,
            phone=phone,
            password=password,
            role_name='Agent'
        )
        if user:
            agent = Agent(
                user_id=user.user_id,
                bank_name=bank_name,
                account_number=account_number,
                status='active'
            )
            db.session.add(agent)
            db.session.commit()

            # Automatically authenticate newly registered agent session
            login_user(user)

            # Trigger SuperAdmin Notification for New Agent Registration
            from app.services import NotificationService
            NotificationService.create_notification(
                notification_type='AGENT_REGISTRATION_SUBMITTED',
                portal='AGENTS',
                title='New Agent Registration',
                message=f"New agent registration submitted for '{full_name}'. Review & verification required.",
                priority='HIGH',
                requires_action=True,
                related_type='Agent',
                related_id=agent.agent_id,
                action_url='/admin/agents'
            )

            referral_link = f"{request.host_url}?ref={agent.agent_code}"
            qr_url, _ = generate_agent_qrcode(agent.agent_code, referral_link)

            try:
                email_msg = Message(
                    subject='Welcome to The Height Agent Partnership',
                    recipients=[email],
                    body=(
                        f"Dear {user.full_name},\n\n"
                        f"Thank you for becoming our official Referral Agent. Your registration has been received successfully.\n\n"
                        f"Welcome as an official Referral Agent of The Height Premium Apartments!\n\n"
                        f"Your Referral Code: {agent.agent_code}\n"
                        f"Your Referral Link: {referral_link}\n"
                        f"Your QR Code Asset: {request.host_url.rstrip('/')}{qr_url}\n\n"
                        f"Instructions: You can now begin referring clients using your unique referral link and referral code.\n\n"
                        f"We appreciate your partnership and wish you success.\n\n"
                        f"Kind regards,\n"
                        f"The Height Apartments Team"
                    )
                )
                threading.Thread(
                    target=_send_async_agent_email,
                    args=(current_app._get_current_object(), email_msg)
                ).start()
            except Exception as e:
                current_app.logger.warning(f"Async email thread creation failed: {e}")

            flash(f'Dear {user.full_name}, your registration has been received.', 'success')
            return redirect(url_for('agents.agent_portal_registered', registered='1', agent_name=user.full_name, agent_code=agent.agent_code))
        else:
            flash(msg, 'danger')
            return redirect(url_for('agents.agent_portal'))

    @app.route('/agents/dashboard', endpoint='agents.dashboard')
    @agent_only
    def agent_dashboard():
        from app.models import Agent, Commission, ReferralHistory
        from app.services import CommissionService

        agent = Agent.query.filter_by(user_id=current_user.user_id).first()
        if not agent:
            flash('Agent profile not found.', 'danger')
            return redirect(url_for('public.home'))

        commissions = Commission.query.filter_by(agent_id=agent.agent_id).order_by(Commission.created_at.desc()).all()
        metrics = CommissionService.get_commission_metrics(agent_id=agent.agent_id)
        referral_clicks = ReferralHistory.query.filter_by(agent_id=agent.agent_id).order_by(ReferralHistory.created_at.desc()).limit(20).all()

        return render_template(
            'dashboard/agent_dashboard.html',
            agent=agent,
            commissions=commissions,
            metrics=metrics,
            referral_clicks=referral_clicks
        )

    @app.route('/agents/api/<int:agent_id>/referral', endpoint='agents.get_agent_referral_api')
    @app.route('/agents/<int:agent_id>/referral', endpoint='agents.get_agent_referral_api_alt')
    def get_agent_referral_api(agent_id):
        agent = Agent.query.get(agent_id)
        if not agent:
            return jsonify({'error': 'Agent not found'}), 404

        user = User.query.get(agent.user_id)
        agent_name = user.full_name if user else 'Agent'
        referral_link = f"{request.host_url}?ref={agent.agent_code}"
        qr_url, _ = generate_agent_qrcode(agent.agent_code, referral_link)

        return jsonify({
            "agent_id": agent.agent_id,
            "agent_name": agent_name,
            "referral_code": agent.agent_code,
            "referral_link": referral_link,
            "qr_code_url": qr_url
        })

    @app.route('/agents/api/<int:agent_id>/referral/qr', endpoint='agents.get_agent_qr_api')
    @app.route('/agents/<int:agent_id>/referral/qr', endpoint='agents.get_agent_qr_api_alt')
    def get_agent_qr_api(agent_id):
        agent = Agent.query.get(agent_id)
        if not agent:
            return jsonify({'error': 'Agent not found'}), 404

        referral_link = f"{request.host_url}?ref={agent.agent_code}"
        _, qr_filepath = generate_agent_qrcode(agent.agent_code, referral_link)
        return send_file(qr_filepath, mimetype='image/png')
