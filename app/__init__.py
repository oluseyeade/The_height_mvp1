import os
from flask import Flask
from config import config
from app.extensions import db, migrate, login_manager, csrf, mail

def create_app(config_name=None):

    app = Flask(__name__)

    if config_name is None:
        config_name = os.getenv("FLASK_CONFIG") or os.getenv("FLASK_ENV") or "production"

    config_name = str(config_name).lower().strip()
    config_class = config.get(
        config_name,
        config.get("production", config.get("default"))
    )

    app.config.from_object(config_class)

    
    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Startup Environment & Configuration Audit Logger
    env_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    env_found = os.path.exists(env_file_path)
    print("========================================================================")
    print("            .ENV ENVIRONMENT & STARTUP CONFIGURATION AUDIT              ")
    print("========================================================================")
    print(f"[OK] .env file found: {'Yes (' + env_file_path + ')' if env_found else 'No'}")
    print(f"[OK] .env successfully loaded: Yes")
    print(f"[OK] Number of environment variables loaded: {len(os.environ)}")
    print(f"[OK] PAYSTACK_SECRET_KEY exists: {'Yes' if app.config.get('PAYSTACK_SECRET_KEY') else 'No'}")
    print(f"[OK] PAYSTACK_PUBLIC_KEY exists: {'Yes' if app.config.get('PAYSTACK_PUBLIC_KEY') else 'No'}")
    print(f"[OK] DATABASE_URL exists: {'Yes' if app.config.get('SQLALCHEMY_DATABASE_URI') else 'No'}")
    print(f"[OK] MAIL configuration loaded: {'Yes' if app.config.get('MAIL_SERVER') and app.config.get('MAIL_USERNAME') else 'No'}")
    print("========================================================================")

    # Configure ProxyFix Middleware for Railway Reverse Proxy Load Balancers
    if app.config.get('USE_PROXY_FIX'):
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

    # Production Structured Stream Logging Setup
    import logging, sys
    if not app.debug:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
        stream_handler.setFormatter(formatter)
        app.logger.addHandler(stream_handler)
        app.logger.setLevel(logging.INFO)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)

    # Ensure database tables exist & seed default data on startup
    with app.app_context():
        try:
            from flask_migrate import upgrade as flask_migrate_upgrade
            flask_migrate_upgrade()
        except Exception as e:
            app.logger.warning(f"[MIGRATION WARNING] Automatic migration warning: {e}")
            try:
                db.create_all()
            except Exception as e2:
                app.logger.error(f"[MIGRATION ERROR] db.create_all error: {e2}")

        try:
            from starter import seed_database
            seed_database(app)
        except Exception as e:
            app.logger.warning(f"[SEED WARNING] Automatic database seeding warning: {e}")

    # HTTP Security Headers Response Hook
    @app.after_request
    def apply_security_headers(response):
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    # Session Referral Capture Hook with Strict Request URL Scope
    @app.before_request
    def capture_referral():
        from flask import request, session
        ref = request.args.get('ref') or request.args.get('referral') or request.args.get('agent_code')
        method = request.args.get('method', 'link')
        if ref is not None:
            ref_str = str(ref).strip()
            if ref_str:
                from app.utils import validate_referral_code, record_referral_history
                agent, is_valid, msg = validate_referral_code(ref_str)
                record_referral_history(ref_str, is_valid, msg, method=method)
                if is_valid and agent:
                    session['referral_code'] = agent.agent_code
                    session['referral_method'] = str(method).strip()
                else:
                    session.pop('referral_code', None)
            else:
                session.pop('referral_code', None)

    # Context Processor for Global Persistent Booking Session, Bank Details & SEO Metadata
    @app.context_processor
    def inject_global_context():
        from app.utils import get_booking_session
        return {
            'booking_session': get_booking_session(),
            'bank_name': app.config.get('BANK_NAME', ''),
            'account_number': app.config.get('ACCOUNT_NUMBER', ''),
            'account_name': app.config.get('ACCOUNT_NAME', ''),
            'ga_measurement_id': app.config.get('GA_MEASUREMENT_ID', ''),
            'google_ads_conversion_id': app.config.get('GOOGLE_ADS_CONVERSION_ID', ''),
            'meta_pixel_id': app.config.get('META_PIXEL_ID', ''),
            'site_url': app.config.get('SITE_URL', 'https://theheightapartment.com')
        }

    # Global CSRF Error Handler
    from flask_wtf.csrf import CSRFError
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        from flask import request, jsonify, flash, redirect, url_for
        is_ajax = request.is_json or request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        msg = 'CSRF verification failed or session expired. Please refresh the page and try again.'
        if is_ajax:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'danger')
        return redirect(request.referrer or url_for('public.index'))

    # Register all routes cleanly without Blueprints
    from app.routes import init_routes
    init_routes(app)

    return app
