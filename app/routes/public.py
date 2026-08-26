from flask import render_template, request, flash, redirect, url_for, jsonify, send_file
from app.models import Agent, User
from app.services import ApartmentService
from app.utils import generate_agent_qrcode, get_booking_session

apt_service = ApartmentService()

def init_public_routes(app):
    @app.route('/health', methods=['GET'], endpoint='public.health')
    def health():
        """Production Health & Database Readiness Probe."""
        from sqlalchemy import text
        from datetime import datetime, timezone
        from app.extensions import db

        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'environment': app.config.get('FLASK_ENV', 'production'),
            'storage_backend': app.config.get('STORAGE_BACKEND', 'local'),
            'database': 'unknown'
        }
        try:
            db.session.execute(text('SELECT 1'))
            health_status['database'] = 'connected'
            return jsonify(health_status), 200
        except Exception:
            health_status['status'] = 'unhealthy'
            health_status['database'] = 'disconnected'
            return jsonify(health_status), 503
        


    @app.route('/', endpoint='public.index')
    def index():
        get_booking_session()
        featured_apartments = apt_service.get_featured_apartments(limit=4)
        return render_template('public/index.html', apartments=featured_apartments)

    @app.route('/contact', methods=['GET', 'POST'], endpoint='public.contact')
    def contact():
        if request.method == 'POST':
            name = request.form.get('name')
            email = request.form.get('email')
            phone = request.form.get('phone')
            message = request.form.get('message')
            flash(f'Thank you, {name}! Your message has been sent to our desk. We will reach out shortly.', 'success')
            return redirect(url_for('public.contact'))

        # Server-Side Location Map Authorization Verification
        from flask_login import current_user
        has_paid_booking = False

        if current_user.is_authenticated:
            if getattr(current_user, 'is_superadmin', False) or getattr(current_user, 'is_admin', False):
                has_paid_booking = True
            else:
                from app.models import Booking
                paid_b = Booking.query.filter(
                    (Booking.user_id == current_user.user_id) |
                    (Booking.guest_email.isnot(None) & (Booking.guest_email == current_user.email)),
                    Booking.status.in_(['confirmed', 'CONFIRMED', 'active', 'ACTIVE', 'checked_in', 'CHECKED_IN', 'completed', 'COMPLETED']),
                    Booking.payment_status.in_(['VERIFIED', 'PAID', 'verified', 'paid'])
                ).first()
                if paid_b:
                    has_paid_booking = True

        return render_template('public/contact.html', has_paid_booking=has_paid_booking)

    @app.route('/faq', endpoint='public.faq')
    def faq():
        return render_template('public/faq.html')

    @app.route('/house-rules', endpoint='public.house_rules')
    def house_rules():
        return render_template('public/house_rules.html')

    @app.route('/cancellation-policy', endpoint='public.cancellation_policy')
    def cancellation_policy():
        return render_template('public/cancellation_policy.html')

    @app.route('/api/agents/<int:agent_id>/referral', endpoint='public.get_agent_referral_root_api')
    def get_agent_referral_root_api(agent_id):
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

    @app.route('/api/agents/<int:agent_id>/referral/qr', endpoint='public.get_agent_qr_root_api')
    def get_agent_qr_root_api(agent_id):
        agent = Agent.query.get(agent_id)
        if not agent:
            return jsonify({'error': 'Agent not found'}), 404

        referral_link = f"{request.host_url}?ref={agent.agent_code}"
        _, qr_filepath = generate_agent_qrcode(agent.agent_code, referral_link)
        return send_file(qr_filepath, mimetype='image/png')

    @app.route('/robots.txt', endpoint='public.robots_txt')
    def robots_txt():
        from flask import Response
        domain = request.host_url.rstrip('/')
        content = f"""User-agent: *
Allow: /
Allow: /apartments/
Allow: /contact
Allow: /faq
Allow: /house-rules
Allow: /cancellation-policy
Allow: /corporate/
Allow: /agents/

Disallow: /admin/
Disallow: /superadmin/
Disallow: /auth/
Disallow: /payments/
Disallow: /bookings/
Disallow: /inspections/
Disallow: /receipts/
Disallow: /api/

Sitemap: {domain}/sitemap.xml
"""
        return Response(content, mimetype='text/plain')

    @app.route('/sitemap.xml', endpoint='public.sitemap_xml')
    def sitemap_xml():
        from flask import Response
        from datetime import datetime
        domain = request.host_url.rstrip('/')
        now_str = datetime.utcnow().strftime('%Y-%m-%d')

        xml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        ]

        static_routes = [
            ('/', '1.0', 'daily'),
            ('/apartments/', '0.9', 'daily'),
            ('/contact', '0.7', 'monthly'),
            ('/faq', '0.6', 'monthly'),
            ('/house-rules', '0.5', 'monthly'),
            ('/cancellation-policy', '0.5', 'monthly'),
            ('/corporate/', '0.8', 'weekly'),
            ('/agents/', '0.8', 'weekly')
        ]

        for path, priority, freq in static_routes:
            xml_lines.append('  <url>')
            xml_lines.append(f'    <loc>{domain}{path}</loc>')
            xml_lines.append(f'    <lastmod>{now_str}</lastmod>')
            xml_lines.append(f'    <changefreq>{freq}</changefreq>')
            xml_lines.append(f'    <priority>{priority}</priority>')
            xml_lines.append('  </url>')

        active_apts = apt_service.get_all_active_apartments()
        for apt in active_apts:
            xml_lines.append('  <url>')
            xml_lines.append(f'    <loc>{domain}/apartments/{apt.apartment_id}</loc>')
            xml_lines.append(f'    <lastmod>{now_str}</lastmod>')
            xml_lines.append(f'    <changefreq>weekly</changefreq>')
            xml_lines.append(f'    <priority>0.9</priority>')
            xml_lines.append('  </url>')

        xml_lines.append('</urlset>')
        xml_content = '\n'.join(xml_lines)
        return Response(xml_content, mimetype='application/xml')
