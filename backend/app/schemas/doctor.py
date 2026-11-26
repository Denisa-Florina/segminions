"""Pydantic models for doctor API responses."""

from pydantic import BaseModel


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
