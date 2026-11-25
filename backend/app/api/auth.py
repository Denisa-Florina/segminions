from flask import Blueprint, jsonify, request, session

from app.core.errors import AuthenticationError, ValidationError
from app.services.auth_service import auth_service

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email, password = data.get("email"), data.get("password")
    if not email or not password:
        raise ValidationError("Email and password are required")

    doctor = auth_service.authenticate(email, password)
    session["doctor_id"] = doctor["id"]
    session["doctor_email"] = doctor["email"]
    return jsonify({"message": "Login successful", "doctor": doctor}), 200


@auth_bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logout successful"}), 200


@auth_bp.get("/me")
def get_current_doctor():
    doctor_id = session.get("doctor_id")
    if not doctor_id:
        raise AuthenticationError("Not authenticated")
    return jsonify({"doctor": auth_service.get_doctor(doctor_id)}), 200
