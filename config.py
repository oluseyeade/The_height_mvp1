import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

def _get_database_url(required=True):
    db_uri = (
        os.environ.get('DATABASE_URL') or 
        os.environ.get('SQLALCHEMY_DATABASE_URI') or 
        os.environ.get('MYSQL_URL') or 
        os.environ.get('MYSQL_PRIVATE_URL') or 
        os.environ.get('DATABASE_PUBLIC_URL')
    )
    if db_uri:
        db_uri = db_uri.strip()

    if db_uri and (db_uri.startswith('your-') or db_uri == 'x'):
        db_uri = None

    if not db_uri:
        user = (os.environ.get('DB_USER') or os.environ.get('MYSQL_USER') or os.environ.get('MYSQLUSER') or 'root').strip()
        password = (os.environ.get('DB_PASSWORD') or os.environ.get('MYSQL_PASSWORD') or os.environ.get('MYSQLPASSWORD') or '').strip()
        host = (os.environ.get('DB_HOST') or os.environ.get('MYSQL_HOST') or os.environ.get('MYSQLHOST') or 'localhost').strip()
        port = (os.environ.get('DB_PORT') or os.environ.get('MYSQL_PORT') or os.environ.get('MYSQLPORT') or '3306').strip()
        name = (os.environ.get('DB_NAME') or os.environ.get('MYSQL_DATABASE') or os.environ.get('MYSQLDATABASE') or os.environ.get('MYSQL_DB') or 'the_height').strip()
        pass_part = f":{password}" if password else ""
        db_uri = f"mysql+mysqlconnector://{user}{pass_part}@{host}:{port}/{name}?use_pure=True"

    if db_uri.startswith('mysql://'):
        db_uri = db_uri.replace('mysql://', 'mysql+mysqlconnector://', 1)

    if '?' not in db_uri and not db_uri.startswith('sqlite'):
        db_uri += '?use_pure=True'

    is_valid_mysql = db_uri and (db_uri.startswith('mysql://') or db_uri.startswith('mysql+mysqlconnector://') or db_uri.startswith('mysql+pymysql://'))

    if required and not is_valid_mysql:
        raise RuntimeError("DATABASE_URL must be set to a real MySQL connection string before starting the app.")

    return db_uri

get_database_uri = _get_database_url

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
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max limit
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
    SQLALCHEMY_DATABASE_URI = _get_database_url(required=False)
    
class ProductionConfig(Config):
    DEBUG = False

    SECRET_KEY = os.environ.get('SECRET_KEY')

    if not SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY must be configured in production."
        )

    SQLALCHEMY_DATABASE_URI = _get_database_url()

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
