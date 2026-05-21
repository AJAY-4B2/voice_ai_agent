"""
API Data Models — Request/Response schemas used across the application.
"""

from datetime import datetime, date
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class AppointmentRequest(BaseModel):
    patient_id: str
    doctor_id: str
    date: date
    time_slot: str  # "HH:MM"
    reason: Optional[str] = None
    language: Literal["en", "hi", "ta"] = "en"


class AppointmentResponse(BaseModel):
    appointment_id: str
    patient_id: str
    doctor_id: str
    doctor_name: str
    date: date
    time_slot: str
    status: Literal["confirmed", "cancelled", "rescheduled", "pending"]
    confirmation_message: str
    language: str


class RescheduleRequest(BaseModel):
    appointment_id: str
    new_date: date
    new_time_slot: str


class CancelRequest(BaseModel):
    appointment_id: str
    reason: Optional[str] = None


class AvailabilityRequest(BaseModel):
    doctor_id: str
    date: date


class AvailabilityResponse(BaseModel):
    doctor_id: str
    doctor_name: str
    date: date
    available_slots: List[str]


class PatientContext(BaseModel):
    patient_id: str
    name: Optional[str] = None
    preferred_language: Literal["en", "hi", "ta"] = "en"
    preferred_doctor: Optional[str] = None
    preferred_hospital: Optional[str] = None
    past_appointments: List[dict] = Field(default_factory=list)


class LatencyMetrics(BaseModel):
    session_id: str
    stt_latency_ms: float
    agent_latency_ms: float
    tts_latency_ms: float
    total_latency_ms: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    met_target: bool = Field(default=False)  # target < 450ms


class CampaignRequest(BaseModel):
    campaign_id: str
    campaign_type: Literal["reminder", "followup", "vaccination"]
    patient_ids: List[str]
    message_template: str
    language: Optional[Literal["en", "hi", "ta"]] = None  # None = use patient preference
    scheduled_at: Optional[datetime] = None


class AgentIntent(BaseModel):
    intent: Literal["book", "cancel", "reschedule", "check_availability", "greeting", "unknown"]
    doctor_type: Optional[str] = None
    doctor_id: Optional[str] = None
    date: Optional[str] = None
    time_slot: Optional[str] = None
    appointment_id: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    language: str = "en"
    raw_text: str = ""


class ConversationTurn(BaseModel):
    role: Literal["user", "agent"]
    text: str
    language: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    intent: Optional[AgentIntent] = None
