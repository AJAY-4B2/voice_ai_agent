"""
Appointment Engine — booking, rescheduling, cancellation, availability.

Storage: In-memory dict + optional PostgreSQL (configurable via DATABASE_URL).
In production, swap to AsyncPG. For demo/test: pure in-memory.

Conflict detection:
  - No double-booking of same slot
  - No bookings in the past
  - Doctor must exist / be available that day
"""

import json
import logging
import os
import uuid
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mock doctor database
# ---------------------------------------------------------------------------

DOCTORS: Dict[str, dict] = {
    "doc_001": {"name": "Dr. Arjun Sharma", "specialty": "cardiologist"},
    "doc_002": {"name": "Dr. Priya Nair", "specialty": "dermatologist"},
    "doc_003": {"name": "Dr. Rakesh Gupta", "specialty": "general physician"},
    "doc_004": {"name": "Dr. Anita Menon", "specialty": "neurologist"},
    "doc_005": {"name": "Dr. Suresh Iyer", "specialty": "orthopedist"},
}

SPECIALTY_TO_DOCTOR = {d["specialty"]: did for did, d in DOCTORS.items()}

DEFAULT_SLOTS = ["09:00", "09:30", "10:00", "10:30", "11:00",
                 "14:00", "14:30", "15:00", "15:30", "16:00", "16:30"]


class AppointmentEngine:
    def __init__(self):
        # In-memory store: appointment_id → AppointmentResponse-like dict
        self._appointments: Dict[str, dict] = {}
        # Booked slots index: "doctor_id:date:time" → appointment_id
        self._slot_index: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Book
    # ------------------------------------------------------------------

    async def book(self, req) -> Optional[object]:
        """Create a new appointment. Returns None on conflict."""
        from backend.api.models import AppointmentResponse

        # Resolve doctor
        doctor = self._resolve_doctor(req.doctor_id)
        if not doctor:
            logger.warning(f"Doctor not found: {req.doctor_id}")
            return None

        doctor_id = doctor["id"]

        # Validate: not in the past
        appt_dt = datetime.combine(req.date, datetime.strptime(req.time_slot, "%H:%M").time())
        if appt_dt < datetime.now():
            logger.warning("Attempted to book past slot")
            return None

        # Conflict check
        slot_key = f"{doctor_id}:{req.date}:{req.time_slot}"
        if slot_key in self._slot_index:
            logger.warning(f"Slot conflict: {slot_key}")
            return None

        appointment_id = str(uuid.uuid4())[:8].upper()
        appt = {
            "appointment_id": appointment_id,
            "patient_id": req.patient_id,
            "doctor_id": doctor_id,
            "doctor_name": doctor["name"],
            "date": req.date,
            "time_slot": req.time_slot,
            "status": "confirmed",
            "reason": getattr(req, "reason", "") or "",
            "confirmation_message": (
                f"Your appointment with {doctor['name']} is confirmed for "
                f"{req.date} at {req.time_slot}."
            ),
            "language": getattr(req, "language", "en"),
        }
        self._appointments[appointment_id] = appt
        self._slot_index[slot_key] = appointment_id
        logger.info(f"Appointment booked: {appointment_id}")

        # Return as Pydantic model
        return AppointmentResponse(**appt)

    # ------------------------------------------------------------------
    # Reschedule
    # ------------------------------------------------------------------

    async def reschedule(self, req) -> Optional[object]:
        from backend.api.models import AppointmentResponse

        appt = self._appointments.get(req.appointment_id)
        if not appt:
            return None

        # Free old slot
        old_key = f"{appt['doctor_id']}:{appt['date']}:{appt['time_slot']}"
        self._slot_index.pop(old_key, None)

        # Validate new slot
        new_dt = datetime.combine(req.new_date, datetime.strptime(req.new_time_slot, "%H:%M").time())
        if new_dt < datetime.now():
            # Restore old slot and reject
            self._slot_index[old_key] = req.appointment_id
            return None

        new_key = f"{appt['doctor_id']}:{req.new_date}:{req.new_time_slot}"
        if new_key in self._slot_index:
            self._slot_index[old_key] = req.appointment_id
            return None

        appt["date"] = req.new_date
        appt["time_slot"] = req.new_time_slot
        appt["status"] = "rescheduled"
        appt["confirmation_message"] = (
            f"Your appointment with {appt['doctor_name']} has been rescheduled to "
            f"{req.new_date} at {req.new_time_slot}."
        )
        self._slot_index[new_key] = req.appointment_id
        return AppointmentResponse(**appt)

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    async def cancel(self, req) -> bool:
        appt = self._appointments.get(req.appointment_id)
        if not appt:
            return False
        slot_key = f"{appt['doctor_id']}:{appt['date']}:{appt['time_slot']}"
        self._slot_index.pop(slot_key, None)
        appt["status"] = "cancelled"
        logger.info(f"Appointment cancelled: {req.appointment_id}")
        return True

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    async def get_availability(self, doctor_id: str, appt_date: date) -> dict:
        doctor = DOCTORS.get(doctor_id)
        if not doctor:
            return {"doctor_id": doctor_id, "doctor_name": "Unknown", "date": appt_date, "available_slots": []}
        available = self._compute_free_slots(doctor_id, appt_date)
        return {
            "doctor_id": doctor_id,
            "doctor_name": doctor["name"],
            "date": appt_date,
            "available_slots": available,
        }

    async def get_availability_by_id_or_specialty(self, identifier: str, date_str: str) -> Optional[dict]:
        """Resolve by doctor_id or specialty string."""
        from datetime import date as date_type
        appt_date = date_type.fromisoformat(date_str)

        doctor = self._resolve_doctor(identifier)
        if not doctor:
            return None

        available = self._compute_free_slots(doctor["id"], appt_date)
        return {
            "doctor_id": doctor["id"],
            "doctor_name": doctor["name"],
            "specialty": doctor.get("specialty"),
            "available_slots": available,
        }

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get(self, appointment_id: str) -> Optional[object]:
        from backend.api.models import AppointmentResponse
        appt = self._appointments.get(appointment_id)
        if not appt:
            return None
        return AppointmentResponse(**appt)

    async def list_by_patient(self, patient_id: str) -> List[dict]:
        return [
            a for a in self._appointments.values()
            if a["patient_id"] == patient_id and a["status"] != "cancelled"
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_doctor(self, identifier: str) -> Optional[dict]:
        """Accept doctor_id or specialty name."""
        if identifier in DOCTORS:
            return {"id": identifier, **DOCTORS[identifier]}
        # Try specialty match
        for did, doc in DOCTORS.items():
            if doc["specialty"].lower() in identifier.lower() or identifier.lower() in doc["specialty"].lower():
                return {"id": did, **doc}
        return None

    def _compute_free_slots(self, doctor_id: str, appt_date: date) -> List[str]:
        prefix = f"{doctor_id}:{appt_date}:"
        booked = set()
        for slot_key in self._slot_index:
            if slot_key.startswith(prefix):
                # Key format: "doc_001:2025-01-15:09:00"
                # Strip prefix to get "09:00"
                time_part = slot_key[len(prefix):]
                booked.add(time_part)
        now = datetime.now()
        free = []
        for s in DEFAULT_SLOTS:
            if s in booked:
                continue
            slot_dt = datetime.combine(appt_date, datetime.strptime(s, "%H:%M").time())
            if slot_dt > now:
                free.append(s)
        return free
