"""Entry point: `gunicorn wsgi:app` in production, `python wsgi.py` locally."""

import os

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402  (must run after load_dotenv)

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
