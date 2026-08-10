from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class SetupInput(APIModel):
    password: str = Field(min_length=10, max_length=256)
    profile_name: str = Field(min_length=1, max_length=200)


class LoginInput(APIModel):
    password: str = Field(min_length=1, max_length=256)


class ProfileInput(APIModel):
    name: str = Field(min_length=1, max_length=200)
    date_of_birth: date | None = None
    blood_group: str | None = Field(default=None, max_length=20)
    allergies: str | None = None
    chronic_conditions: str | None = None
    emergency_information: str | None = None
    notes: str | None = None
    color: str = Field(default="#27786d", pattern=r"^#[0-9a-fA-F]{6}$")


class ProviderInput(APIModel):
    name: str = Field(min_length=1, max_length=200)
    specialty: str | None = Field(default=None, max_length=160)
    hospital: str | None = Field(default=None, max_length=240)
    phone: str | None = Field(default=None, max_length=80)
    address: str | None = None
    notes: str | None = None


class VisitInput(APIModel):
    profile_id: str
    provider_id: str | None = None
    visit_date: datetime
    reason: str | None = None
    symptoms: str | None = None
    clinical_impression: str | None = None
    diagnosis_text: str | None = None
    follow_up_date: datetime | None = None
    summary: str | None = None
    notes: str | None = None
    appointment_id: str | None = None


class PrescriptionInput(APIModel):
    profile_id: str
    visit_id: str | None = None
    provider_id: str | None = None
    document_id: str | None = None
    prescription_date: date
    status: Literal["unverified", "verified", "corrected"] = "unverified"
    diagnosis_text: str | None = None
    notes: str | None = None


class MedicationInput(APIModel):
    generic_name: str | None = Field(default=None, max_length=240)
    brand_name: str | None = Field(default=None, max_length=240)
    strength: str | None = Field(default=None, max_length=100)
    form: str | None = Field(default=None, max_length=100)
    manufacturer: str | None = Field(default=None, max_length=200)
    notes: str | None = None

    @field_validator("brand_name")
    @classmethod
    def at_least_one_name(cls, value: str | None, info: Any) -> str | None:
        if not value and not info.data.get("generic_name"):
            raise ValueError("generic_name or brand_name is required")
        return value


class PrescribedMedicationInput(APIModel):
    prescription_id: str | None = None
    profile_id: str
    medication_id: str
    dosage: str | None = None
    frequency: str | None = None
    timing: str | None = None
    duration: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    food_relation: str | None = None
    instructions: str | None = None
    as_needed: bool = False
    verification_status: Literal["unverified", "verified", "corrected"] = "unverified"
    tracking_status: Literal["active", "completed", "stopped"] = "active"
    schedule: dict[str, Any] = Field(default_factory=dict)


class AppointmentInput(APIModel):
    profile_id: str
    provider_id: str | None = None
    starts_at: datetime
    purpose: str | None = None
    location: str | None = Field(default=None, max_length=300)
    preparation_notes: str | None = None
    documents_to_carry: str | None = None
    reminder_minutes: int = Field(default=1440, ge=0, le=525600)
    status: Literal["scheduled", "completed", "cancelled", "follow_up_required"] = "scheduled"
    post_visit_notes: str | None = None


class NoteInput(APIModel):
    profile_id: str
    visit_id: str | None = None
    prescribed_medication_id: str | None = None
    occurred_at: datetime | None = None
    title: str | None = Field(default=None, max_length=240)
    content: str = Field(min_length=1)


class ObservationInput(APIModel):
    profile_id: str
    observed_at: datetime | None = None
    kind: str = Field(min_length=1, max_length=80)
    value: float
    unit: str = Field(min_length=1, max_length=40)
    secondary_value: float | None = None
    notes: str | None = None


class ReminderInput(APIModel):
    profile_id: str
    prescribed_medication_id: str | None = None
    appointment_id: str | None = None
    kind: Literal["medication", "appointment", "follow_up", "lab_test", "check_up", "renewal", "custom"]
    title: str = Field(min_length=1, max_length=240)
    due_at: datetime
    recurrence: dict[str, Any] = Field(default_factory=dict)
    status: Literal["pending", "completed", "missed", "snoozed", "cancelled"] = "pending"
    snoozed_until: datetime | None = None
    notes: str | None = None


class DoseEventInput(APIModel):
    prescribed_medication_id: str
    scheduled_at: datetime
    status: Literal["taken", "skipped"]
    note: str | None = None


class BackupDestinationInput(APIModel):
    name: str = Field(min_length=1, max_length=200)
    path: str = Field(min_length=1, max_length=1000)
    role: Literal["primary", "secondary", "archive"] = "primary"
    enabled: bool = True


class BackupCreateInput(APIModel):
    password: str = Field(min_length=12, max_length=256)
    kind: Literal["manual", "daily", "weekly", "monthly", "emergency"] = "manual"


class BackupPasswordInput(APIModel):
    path: str
    password: str = Field(min_length=1, max_length=256)


class AIQueryInput(APIModel):
    question: str = Field(min_length=2, max_length=2000)
    profile_id: str | None = None


class ExtractionProposal(APIModel):
    patient: dict[str, Any] | None = None
    visit: dict[str, Any] | None = None
    symptoms: list[dict[str, Any]] = Field(default_factory=list)
    diagnosis_text: list[dict[str, Any]] = Field(default_factory=list)
    medications: list[dict[str, Any]] = Field(default_factory=list)
    tests: list[dict[str, Any]] = Field(default_factory=list)
    follow_up: dict[str, Any] | None = None
    uncertain_fields: list[str] = Field(default_factory=list)
    confidence: dict[str, float] = Field(default_factory=dict)


class ExtractionUpdate(APIModel):
    proposal: ExtractionProposal
    status: Literal["unverified", "verified", "corrected"]


class ImportOptions(APIModel):
    dry_run: bool = True
