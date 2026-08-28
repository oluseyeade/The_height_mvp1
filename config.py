import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'), override=False)

def _is_localhost(val):
    if not val:
        return False
    s = str(val).lower().strip()
    return 'localhost' in s or '127.0.0.1' in s

def _log_safe_db_diagnostics(db_uri, source, is_production):
    try:
        db_url_present = "YES" if os.environ.get('DATABASE_URL') else "NO"
        mysql_url_present = "YES" if os.environ.get('MYSQL_URL') else "NO"
        mysql_private_url_present = "YES" if os.environ.get('MYSQL_PRIVATE_URL') else "NO"
        mysql_host_present = "YES" if (os.environ.get('MYSQLHOST') or os.environ.get('MYSQLPRIVATEHOST') or os.environ.get('MYSQL_HOST')) else "NO"
        railway_env_present = "YES" if (os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RAILWAY_ENVIRONMENT_NAME') or os.environ.get('RAILWAY_SERVICE_ID')) else "NO"

        host = 'N/A'
        port = 'N/A'
        if db_uri and '://' in db_uri:
            rest = db_uri.split('://', 1)[1]
            if '@' in rest:
                host_part = rest.split('@', 1)[1]
            else:
                host_part = rest
            if '/' in host_part:
                hp = host_part.split('/', 1)[0]
            else:
                hp = host_part
            if ':' in hp:
                host, port = hp.split(':', 1)
            else:
                host = hp

        print("========================================================================")
        print("              DATABASE CONFIGURATION RESOLUTION DIAGNOSTICS              ")
        print("========================================================================")
        print(f"[INFO] Mode: {'RAILWAY PRODUCTION' if is_production else 'LOCAL DEVELOPMENT'}")
        print(f"[INFO] DATABASE_URL present: {db_url_present}")
        print(f"[INFO] MYSQL_URL present: {mysql_url_present}")
        print(f"[INFO] MYSQL_PRIVATE_URL present: {mysql_private_url_present}")
        print(f"[INFO] MYSQLHOST present: {mysql_host_present}")
        print(f"[INFO] Railway environment: {railway_env_present}")
        print(f"[INFO] Database Source Selected: {source}")
        print(f"[INFO] Resolved database host: {host}")
        print(f"[INFO] Resolved database port: {port}")
        print("========================================================================")
    except Exception as e:
        print(f"[DIAGNOSTICS WARNING] Could not parse DB URI for logging: {e}")

def get_development_database_url():
    env_db_url = os.environ.get('DATABASE_URL', '').strip()
    if env_db_url and not (env_db_url.startswith('your-') or env_db_url == 'x'):
        db_uri = env_db_url
        resolved_source = 'DATABASE_URL'
    else:
        host = (os.environ.get('DB_HOST') or 'localhost').strip()
        user = (os.environ.get('DB_USER') or 'root').strip()
        password = (os.environ.get('DB_PASSWORD') or '').strip()
        port = (os.environ.get('DB_PORT') or '').strip()
        name = (os.environ.get('DB_NAME') or 'the_height').strip()

        pass_part = f":{password}" if password else ""
        port_part = f":{port}" if port else ""
        db_uri = f"mysql+mysqlconnector://{user}{pass_part}@{host}{port_part}/{name}"
        resolved_source = 'Local Development Config'

    if db_uri.startswith('mysql://'):
        db_uri = db_uri.replace('mysql://', 'mysql+mysqlconnector://', 1)

    if '?' not in db_uri and not db_uri.startswith('sqlite'):
        db_uri += '?use_pure=True'

    _log_safe_db_diagnostics(db_uri, resolved_source, is_production=False)
    return db_uri

def get_production_database_url():
    is_prod_env = (
        os.environ.get('FLASK_ENV') == 'production' or
        os.environ.get('FLASK_CONFIG') == 'production' or
        os.environ.get('RAILWAY_ENVIRONMENT') is not None or
        os.environ.get('RAILWAY_ENVIRONMENT_NAME') is not None or
        os.environ.get('RAILWAY_SERVICE_ID') is not None
    )

    resolved_source = None
    db_uri = None

    # Priority 1: DATABASE_URL / DATABASE_PRIVATE_URL / DATABASE_PUBLIC_URL
    for var_name in ['DATABASE_URL', 'DATABASE_PRIVATE_URL', 'DATABASE_PUBLIC_URL']:
        val = os.environ.get(var_name, '').strip()
        if val and not (val.startswith('your-') or val == 'x'):
            if not (is_prod_env and _is_localhost(val)):
                db_uri = val
                resolved_source = var_name
                break

    # Priority 2: MYSQL_URL / MYSQL_PRIVATE_URL / MYSQL_PUBLIC_URL / SQLALCHEMY_DATABASE_URI
    if not db_uri:
        for var_name in ['MYSQL_URL', 'MYSQL_PRIVATE_URL', 'MYSQL_PUBLIC_URL', 'SQLALCHEMY_DATABASE_URI']:
            val = os.environ.get(var_name, '').strip()
            if val and not (val.startswith('your-') or val == 'x'):
                if not (is_prod_env and _is_localhost(val)):
                    db_uri = val
                    resolved_source = var_name
                    break

    # Priority 4: Component variables (MYSQLHOST / MYSQLPRIVATEHOST / MYSQL_HOST)
    if not db_uri:
        host = (os.environ.get('MYSQLHOST') or os.environ.get('MYSQLPRIVATEHOST') or os.environ.get('MYSQL_HOST') or '').strip()
        if host and not (is_prod_env and _is_localhost(host)):
            user = (os.environ.get('MYSQLUSER') or os.environ.get('MYSQL_USER') or 'root').strip()
            password = (os.environ.get('MYSQLPASSWORD') or os.environ.get('MYSQL_PASSWORD') or '').strip()
            port = (os.environ.get('MYSQLPORT') or os.environ.get('MYSQL_PORT') or '').strip()
            name = (os.environ.get('MYSQLDATABASE') or os.environ.get('MYSQL_DATABASE') or os.environ.get('MYSQL_DB') or 'railway').strip()

            pass_part = f":{password}" if password else ""
            port_part = f":{port}" if port else ""
            db_uri = f"mysql+mysqlconnector://{user}{pass_part}@{host}{port_part}/{name}"
            resolved_source = 'MYSQLHOST/Component Variables'

    # Fail fast in Railway production if no valid production URL exists or host resolves to localhost
    if is_prod_env and (not db_uri or _is_localhost(db_uri)):
        raise RuntimeError(
            "Production database configuration is missing. "
            "Set Railway DATABASE_URL or MYSQL_URL, or provide MYSQLHOST, MYSQLPORT, MYSQLUSER, MYSQLPASSWORD and MYSQLDATABASE."
        )

    if not db_uri:
        db_uri = "mysql+mysqlconnector://root@localhost/the_height"
        resolved_source = 'Local Development Fallback'

    if db_uri.startswith('mysql://'):
        db_uri = db_uri.replace('mysql://', 'mysql+mysqlconnector://', 1)

    if '?' not in db_uri and not db_uri.startswith('sqlite'):
        db_uri += '?use_pure=True'

    _log_safe_db_diagnostics(db_uri, resolved_source, is_production=is_prod_env)
    return db_uri

_get_database_url = get_production_database_url
get_database_uri = get_production_database_url

class Config:
    FLASK_APP = os.environ.get('FLASK_APP', 'starter.py')
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Official Bank Details (Single Source of Truth)
    BANK_NAME = os.environ.get('BANK_NAME', '')
    ACCOUNT_NUMBER = os.environ.get('ACCOUNT_NUMBER', '')
    ACCOUNT_NAME = os.environ.get('ACCOUNT_NAME', '')

    # File upload configurations
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', str(16 * 1024 * 1024)))
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

    # Mail configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'notifications@theheightapartment.com')

    # Paystack configuration
    PAYSTACK_PUBLIC_KEY = os.environ.get('PAYSTACK_PUBLIC_KEY', '')
    PAYSTACK_SECRET_KEY = os.environ.get('PAYSTACK_SECRET_KEY', '')
    PAYSTACK_CALLBACK_URL = os.environ.get('PAYSTACK_CALLBACK_URL', '')
    PAYSTACK_WEBHOOK_SECRET = os.environ.get('PAYSTACK_WEBHOOK_SECRET', '')
    PAYSTACK_INITIALIZE_URL = os.environ.get('PAYSTACK_INITIALIZE_URL', 'https://api.paystack.co/transaction/initialize')
    PAYSTACK_VERIFY_URL = os.environ.get('PAYSTACK_VERIFY_URL', 'https://api.paystack.co/transaction/verify')

    # Redis & Background Tasks configuration
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

    # Technical SEO, Web Analytics & Ads Configuration
    GA_MEASUREMENT_ID = os.environ.get('GA_MEASUREMENT_ID', '')
    GOOGLE_ADS_CONVERSION_ID = os.environ.get('GOOGLE_ADS_CONVERSION_ID', '')
    META_PIXEL_ID = os.environ.get('META_PIXEL_ID', '')
    SITE_URL = os.environ.get('SITE_URL', 'https://theheightapartment.com')

    # WhatsApp API configuration
    WHATSAPP_API_TOKEN = os.environ.get('WHATSAPP_API_TOKEN', '')
    WHATSAPP_PHONE_NUMBER = os.environ.get('WHATSAPP_PHONE_NUMBER', '')

    # Local Upload Storage Backend Configuration
    STORAGE_BACKEND = os.environ.get('STORAGE_BACKEND', 'local').lower()

    # Security & Reverse Proxy Settings
    USE_PROXY_FIX = os.environ.get('USE_PROXY_FIX', 'True').lower() in ['true', 'on', '1']
    PREFERRED_URL_SCHEME = os.environ.get('PREFERRED_URL_SCHEME', 'https')
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # SQLAlchemy Production Connection Pool Settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', 280)),
        'pool_pre_ping': True,
        'pool_size': int(os.environ.get('DB_POOL_SIZE', 10)),
        'max_overflow': int(os.environ.get('DB_MAX_OVERFLOW', 20))
    }

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = get_development_database_url()

class ProductionConfig(Config):
    DEBUG = False

    SECRET_KEY = os.environ.get('SECRET_KEY')

    if not SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY must be configured in production."
        )

    SQLALCHEMY_DATABASE_URI = get_production_database_url()

    SESSION_COOKIE_SECURE = os.environ.get(
        'SESSION_COOKIE_SECURE', 'True'
    ).lower() in ['true', 'on', '1']

    SESSION_COOKIE_SAMESITE = 'Lax'

    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'

class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL', 'sqlite:///test_runner.db')
    SQLALCHEMY_ENGINE_OPTIONS = {}

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
