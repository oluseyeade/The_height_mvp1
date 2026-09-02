import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'), override=False)

from app import create_app

env_name = os.getenv('FLASK_CONFIG') or os.getenv('FLASK_ENV')
app = create_app(env_name)

if __name__ == '__main__':
    print("[OK] Starting local Flask server on http://127.0.0.1:5050")
    app.run(host='127.0.0.1', port=5050, debug=True)