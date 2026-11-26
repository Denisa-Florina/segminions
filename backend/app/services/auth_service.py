"""Doctor authentication."""

import logging

from app.core.errors import AuthenticationError, NotFoundError
from app.core.security import hash_password, is_legacy_hash, verify_password
from app.repositories.doctor_repository import DoctorRepository

logger = logging.getLogger(__name__)

INVALID_CREDENTIALS = "Invalid email or password"

# Checked when the email is unknown, so both failure cases take the same time.
_DUMMY_HASH = hash_password("dummy-password")


def normalize_email(email: str) -> str:
    """Emails are compared case-insensitively: `Ana.Pop@x.ro` == `ana.pop@x.ro`."""
    return email.strip().lower()


def _without_password(doctor: dict) -> dict:
    return {key: value for key, value in doctor.items() if key != "password"}


class AuthService:
    def __init__(self, doctors: DoctorRepository):
        self.doctors = doctors

    def authenticate(self, email: str, password: str) -> dict:
        normalized = normalize_email(email)
        doctor = self._find_by_email(email, normalized)
        if not doctor:
            verify_password(password, _DUMMY_HASH)
            raise AuthenticationError(INVALID_CREDENTIALS)

        stored_hash = doctor.get("password")
        if not verify_password(password, stored_hash):
            raise AuthenticationError(INVALID_CREDENTIALS)

        if is_legacy_hash(stored_hash):
            self.doctors.update_password_hash(doctor["id"], hash_password(password))
            logger.info("Upgraded password hash to bcrypt for doctor %s", doctor["id"])
        if doctor.get("email") != normalized:
            self.doctors.update_email(doctor["id"], normalized)
            logger.info("Normalised the stored email of doctor %s", doctor["id"])
            doctor = {**doctor, "email": normalized}

        return _without_password(doctor)

    def _find_by_email(self, typed: str, normalized: str) -> dict | None:
        """Look up the normalised email. Accounts created before normalisation may be
        stored with capitals: they are found by the address exactly as typed, and their
        stored email is normalised on that first login."""
        doctor = self.doctors.get_by_email(normalized)
        if doctor is None and typed.strip() != normalized:
            doctor = self.doctors.get_by_email(typed.strip())
        return doctor

    def get_doctor(self, doctor_id: str) -> dict:
        doctor = self.doctors.get_by_id(doctor_id)
        if not doctor:
            raise NotFoundError("Doctor not found")
        return _without_password(doctor)


auth_service = AuthService(DoctorRepository())
