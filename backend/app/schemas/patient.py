"""Pydantic models for patient input validation and API responses."""

from typing import Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError
from pydantic.alias_generators import to_camel

from app.core.errors import ValidationError

MIN_AGE, MAX_AGE = 1, 150
MAX_NAME_LENGTH = 100

ModelT = TypeVar("ModelT", bound=BaseModel)


def validate_input(model: type[ModelT], data: dict) -> ModelT:
    """Validate request data, turning Pydantic errors into a 400 with a readable message."""
    try:
        return model.model_validate(data)
    except PydanticValidationError as error:
        first = error.errors()[0]
        field = ".".join(str(part) for part in first["loc"]) or "body"
        if first["type"] == "missing" or first.get("input", "") is None:
            raise ValidationError(f"{field} is required") from None
        raise ValidationError(f"{field}: {first['msg']}") from None


# --- Input -----------------------------------------------------------------

class PatientCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    age: int = Field(ge=MIN_AGE, le=MAX_AGE)
    doctor_id: str = Field(min_length=1)


class PatientUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    name: str | None = Field(default=None, min_length=1, max_length=MAX_NAME_LENGTH)
    age: int | None = Field(default=None, ge=MIN_AGE, le=MAX_AGE)


# --- Output ----------------------------------------------------------------

class SegmentationMetrics(BaseModel):
    # Keys stay snake_case and unknown keys are kept: the frontend reads them as stored.
    model_config = ConfigDict(extra="allow")

    confidence: float = 0
    voxel_count: int | None = None
    volume_mm3: float | None = None
    coverage: float | None = None
    artery_detected: bool | None = None
    simulated: bool = False


class PatientSummary(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    name: str
    age: int
    date: str
    dicom_file: str = ""
    status: Literal["pending", "processing", "completed", "failed"]
    confidence: float = 0
    simulated: bool = False
    segmentation_error: str | None = None

    @classmethod
    def from_db(cls, patient: dict):
        metrics = patient.get("metrics") or {}
        # Patients created before statuses were stored: derive it from `segmented`.
        status = patient.get("status") or ("completed" if patient.get("segmented") else "pending")
        return cls.model_validate({
            **patient,
            "metrics": metrics,
            "status": status,
            "dicom_file": patient.get("filename") or patient.get("dicom_file") or "",
            "confidence": metrics.get("confidence", 0),
            "simulated": bool(metrics.get("simulated")),
        })

    def to_json(self) -> dict:
        return self.model_dump(by_alias=True)


class PatientDetail(PatientSummary):
    metrics: SegmentationMetrics = Field(default_factory=SegmentationMetrics)
