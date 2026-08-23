import os
from datetime import timedelta

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))


def _get_database_url() -> str:
    database_url = os.getenv('DATABASE_URL', '').strip()
    if not database_url:
        raise RuntimeError('DATABASE_URL must be configured in the environment for MySQL access.')

    placeholder_tokens = ('<username>', '<password>', '<host>', '<database>')
    if any(token in database_url for token in placeholder_tokens):
        raise RuntimeError('DATABASE_URL must be set to a real MySQL connection string before starting the app.')

    if not database_url.startswith('mysql+mysqlconnector://'):
        raise RuntimeError('DATABASE_URL must use the mysql+mysqlconnector:// scheme only.')
    return database_url


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'the-height-apartment-default-secret-key-2026')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # File uploads
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'pkg', 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max limit
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'pdf'}

    # Flask-Mail
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 25))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'False').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@theheightapartment.com')

    # Session Security
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = _get_database_url()


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = os.getenv('TEST_DATABASE_URL') or _get_database_url()


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = _get_database_url()


config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
