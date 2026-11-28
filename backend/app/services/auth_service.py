"""Doctor authentication."""

from app.core.clock import utc_now
from app.core.errors import AuthenticationError, ConflictError, NotFoundError
from app.core.security import hash_password, verify_password
from app.repositories.doctor_repository import DoctorRepository
from app.schemas.doctor import DoctorRegister

INVALID_CREDENTIALS = "Invalid email or password"
EMAIL_TAKEN = "An account with this email already exists"

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
        doctor = self.doctors.get_by_email(normalize_email(email))
        if not doctor:
            verify_password(password, _DUMMY_HASH)
            raise AuthenticationError(INVALID_CREDENTIALS)

        if not verify_password(password, doctor.get("password")):
            raise AuthenticationError(INVALID_CREDENTIALS)
        return _without_password(doctor)

    def register(self, data: DoctorRegister) -> dict:
        """Create a doctor account. The email is already normalised by DoctorRegister.

        Known limitation: Firestore has no unique constraint, so two registrations with
        the same email at the same instant could both pass the check below. Closing that
        gap needs a document keyed by the email, created atomically.
        """
        if self.doctors.get_by_email(data.email):
            raise ConflictError(EMAIL_TAKEN)

        doctor = self.doctors.create({
            **data.model_dump(exclude={"password"}),
            "password": hash_password(data.password),
            "created_at": utc_now(),
        })
        return _without_password(doctor)

    def get_doctor(self, doctor_id: str) -> dict:
        doctor = self.doctors.get_by_id(doctor_id)
        if not doctor:
            raise NotFoundError("Doctor not found")
        return _without_password(doctor)


auth_service = AuthService(DoctorRepository())
