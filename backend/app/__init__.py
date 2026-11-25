"""MedSeg AI backend – Flask application factory."""

import logging

from flask import Flask
from flask_cors import CORS

from app.api import register_blueprints
from app.config import Config, get_config
from app.core.errors import register_error_handlers
from app.extensions import init_firebase, init_segmenter


def create_app(config_class: type[Config] | None = None) -> Flask:
    config_class = config_class or get_config()

    app = Flask(__name__)
    app.config.from_object(config_class)
    if not app.config["SECRET_KEY"]:
        raise RuntimeError("SECRET_KEY environment variable is not set")

    logging.basicConfig(
        level=app.config["LOG_LEVEL"],
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    # Auth uses a Bearer token in the Authorization header, not cookies.
    CORS(
        app,
        origins=app.config["CORS_ORIGINS"],
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    )

    if app.config["INIT_FIREBASE"]:
        init_firebase(app)
    if app.config["LOAD_MODEL"]:
        init_segmenter(app)

    register_error_handlers(app)
    register_blueprints(app)
    return app
