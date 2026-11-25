from app.api.auth import auth_bp
from app.api.health import health_bp
from app.api.patients import patients_bp


def register_blueprints(app) -> None:
    for blueprint in (health_bp, auth_bp, patients_bp):
        app.register_blueprint(blueprint)
