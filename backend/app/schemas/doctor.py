"""Pydantic models for doctor registration and API responses."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_NAME_LENGTH = 100
MAX_EMAIL_LENGTH = 254  # the longest address SMTP allows
MIN_PASSWORD_LENGTH = 8
# bcrypt only uses the first 72 bytes of a password: anything longer would be silently
# cut, so two different long passwords could both log in.
MAX_PASSWORD_BYTES = 72


class DoctorRegister(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    email: str = Field(max_length=MAX_EMAIL_LENGTH)
    # Not stripped (unlike the other fields): spaces in a password are kept as typed.
    password: str = Field(min_length=MIN_PASSWORD_LENGTH)
    specialization: str | None = Field(default=None, max_length=MAX_NAME_LENGTH)
    hospital: str | None = Field(default=None, max_length=MAX_NAME_LENGTH)

    @field_validator("name", "email", "specialization", "hospital", mode="before")
    @classmethod
    def strip(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def email_looks_valid(cls, email: str) -> str:
        # A light check (one "@", a dot in the domain, no spaces); full validation
        # would need the email-validator package.
        local, _, domain = email.partition("@")
        if not local or "." not in domain.strip(".") or " " in email or "@" in domain:
            raise ValueError("not a valid email address")
        # Stored lower-case, as login compares emails case-insensitively.
        return email.lower()

    @field_validator("password", mode="before")
    @classmethod
    def password_fits_bcrypt(cls, password):
        if isinstance(password, str) and len(password.encode()) > MAX_PASSWORD_BYTES:
            raise ValueError(f"must be at most {MAX_PASSWORD_BYTES} bytes")
        return password

    @field_validator("specialization", "hospital")
    @classmethod
    def empty_is_none(cls, value: str | None) -> str | None:
        return value or None


class DoctorOut(BaseModel):
    """The doctor fields a client may see. A whitelist: fields added to the doctor
    document later (tokens, roles, ...) are never sent unless they are listed here."""

    id: str
    name: str = ""
    email: str = ""
    specialization: str | None = None
    hospital: str | None = None

    @classmethod
    def from_db(cls, doctor: dict) -> "DoctorOut":
        return cls.model_validate(doctor)

    def to_json(self) -> dict:
        return self.model_dump()
