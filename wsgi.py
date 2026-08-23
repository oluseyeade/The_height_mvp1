import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

from pkg import create_app

application = create_app(os.getenv('FLASK_ENV', 'production'))

if __name__ == '__main__':
    application.run()
