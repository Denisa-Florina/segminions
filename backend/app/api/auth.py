from flask import Blueprint, jsonify, request

from app.core.errors import ValidationError
from app.core.security import create_access_token, current_doctor_id, require_authentication
from app.services.auth_service import auth_service

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email, password = data.get("email"), data.get("password")
    if not email or not password:
        raise ValidationError("Email and password are required")

    doctor = auth_service.authenticate(email, password)
    return jsonify({
        "message": "Login successful",
        "doctor": doctor,
        "token": create_access_token(doctor["id"]),
    }), 200


@auth_bp.post("/logout")
def logout():
    # Tokens are stateless: logging out means the client discards its token.
    return jsonify({"message": "Logout successful"}), 200


@auth_bp.get("/me")
def get_current_doctor():
    require_authentication()
    return jsonify({"doctor": auth_service.get_doctor(current_doctor_id())}), 200
