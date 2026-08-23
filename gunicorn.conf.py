import os

# Railway provides PORT automatically.
PORT = int(os.environ.get("PORT", "5000"))

bind = f"0.0.0.0:{PORT}"

workers = int(os.environ.get("WEB_CONCURRENCY", "4"))

threads = int(os.environ.get("GUNICORN_THREADS", "2"))

timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))

graceful_timeout = int(
    os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", "30")
)

keepalive = int(
    os.environ.get("GUNICORN_KEEPALIVE", "5")
)

accesslog = "-"
errorlog = "-"

loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")