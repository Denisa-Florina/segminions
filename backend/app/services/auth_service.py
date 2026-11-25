"""Doctor authentication."""

import hashlib

from app.core.errors import AuthenticationError, NotFoundError
from app.repositories.doctor_repository import DoctorRepository


def _without_password(doctor: dict) -> dict:
    return {key: value for key, value in doctor.items() if key != "password"}


class AuthService:
    def __init__(self, doctors: DoctorRepository):
        self.doctors = doctors

    def authenticate(self, email: str, password: str) -> dict:
        doctor = self.doctors.get_by_email(email)
        if not doctor:
            raise AuthenticationError("Doctor not found")

        # Unsalted SHA-256 matches the hashes currently stored in Firestore.
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if doctor.get("password") != password_hash:
            raise AuthenticationError("Invalid password")

        return _without_password(doctor)

    def get_doctor(self, doctor_id: str) -> dict:
        doctor = self.doctors.get_by_id(doctor_id)
        if not doctor:
            raise NotFoundError("Doctor not found")
        return _without_password(doctor)


auth_service = AuthService(DoctorRepository())
