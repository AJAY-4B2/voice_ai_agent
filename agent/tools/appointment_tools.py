"""
Appointment tools exposed to the LLM for structured tool calling.
Implements both Anthropic and OpenAI tool definition formats.
"""

from datetime import date, datetime
from typing import Any
import logging

logger = logging.getLogger(__name__)


class AppointmentTools:
    def __init__(self, appointment_engine):
        self.engine = appointment_engine

    # ------------------------------------------------------------------
    # Tool definitions — Anthropic format
    # ------------------------------------------------------------------

    def get_tool_definitions(self) -> list:
        return [
            {
                "name": "check_availability",
                "description": "Check available time slots for a doctor on a given date.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "doctor_id": {"type": "string", "description": "Doctor ID or specialty (e.g. 'cardiologist', 'doc_001')"},
                        "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                    },
                    "required": ["doctor_id", "date"],
                },
            },
            {
                "name": "book_appointment",
                "description": "Book a clinical appointment for the patient.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "patient_id": {"type": "string"},
                        "doctor_id": {"type": "string", "description": "Doctor ID or specialty"},
                        "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                        "time_slot": {"type": "string", "description": "Time in HH:MM format"},
                        "reason": {"type": "string", "description": "Optional reason for visit"},
                    },
                    "required": ["patient_id", "doctor_id", "date", "time_slot"],
                },
            },
            {
                "name": "cancel_appointment",
                "description": "Cancel an existing appointment.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "appointment_id": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["appointment_id"],
                },
            },
            {
                "name": "reschedule_appointment",
                "description": "Reschedule an existing appointment to a new date and time.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "appointment_id": {"type": "string"},
                        "new_date": {"type": "string", "description": "New date YYYY-MM-DD"},
                        "new_time_slot": {"type": "string", "description": "New time HH:MM"},
                    },
                    "required": ["appointment_id", "new_date", "new_time_slot"],
                },
            },
            {
                "name": "get_patient_appointments",
                "description": "Retrieve all upcoming appointments for the patient.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "patient_id": {"type": "string"},
                    },
                    "required": ["patient_id"],
                },
            },
        ]

    def get_openai_tool_definitions(self) -> list:
        """Convert to OpenAI function calling format."""
        result = []
        for t in self.get_tool_definitions():
            result.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            })
        return result

    # ------------------------------------------------------------------
    # Tool execution dispatcher
    # ------------------------------------------------------------------

    async def execute(self, tool_name: str, args: dict) -> dict:
        logger.info(f"Tool call: {tool_name}({args})")
        try:
            if tool_name == "check_availability":
                return await self._check_availability(**args)
            elif tool_name == "book_appointment":
                return await self._book_appointment(**args)
            elif tool_name == "cancel_appointment":
                return await self._cancel_appointment(**args)
            elif tool_name == "reschedule_appointment":
                return await self._reschedule_appointment(**args)
            elif tool_name == "get_patient_appointments":
                return await self._get_patient_appointments(**args)
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            logger.error(f"Tool {tool_name} error: {e}", exc_info=True)
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # Individual tool implementations
    # ------------------------------------------------------------------

    async def _check_availability(self, doctor_id: str, date: str) -> dict:
        slots = await self.engine.get_availability_by_id_or_specialty(doctor_id, date)
        if not slots:
            return {
                "available": False,
                "doctor_id": doctor_id,
                "date": date,
                "message": "No slots available",
            }
        return {
            "available": True,
            "doctor_id": slots["doctor_id"],
            "doctor_name": slots["doctor_name"],
            "date": date,
            "available_slots": slots["available_slots"],
        }

    async def _book_appointment(
        self,
        patient_id: str,
        doctor_id: str,
        date: str,
        time_slot: str,
        reason: str = "",
    ) -> dict:
        from backend.api.models import AppointmentRequest
        from datetime import date as date_type
        req = AppointmentRequest(
            patient_id=patient_id,
            doctor_id=doctor_id,
            date=date_type.fromisoformat(date),
            time_slot=time_slot,
            reason=reason,
        )
        result = await self.engine.book(req)
        if not result:
            # Get alternatives
            alts = await self.engine.get_availability_by_id_or_specialty(doctor_id, date)
            return {
                "error": "slot_unavailable",
                "message": "That slot is already booked.",
                "alternatives": alts.get("available_slots", []) if alts else [],
            }
        return {
            "appointment_id": result.appointment_id,
            "doctor_name": result.doctor_name,
            "date": str(result.date),
            "time_slot": result.time_slot,
            "status": result.status,
        }

    async def _cancel_appointment(self, appointment_id: str, reason: str = "") -> dict:
        from backend.api.models import CancelRequest
        ok = await self.engine.cancel(CancelRequest(appointment_id=appointment_id, reason=reason))
        if not ok:
            return {"error": "not_found", "message": "Appointment not found."}
        return {"status": "cancelled", "appointment_id": appointment_id}

    async def _reschedule_appointment(
        self, appointment_id: str, new_date: str, new_time_slot: str
    ) -> dict:
        from backend.api.models import RescheduleRequest
        from datetime import date as date_type
        req = RescheduleRequest(
            appointment_id=appointment_id,
            new_date=date_type.fromisoformat(new_date),
            new_time_slot=new_time_slot,
        )
        result = await self.engine.reschedule(req)
        if not result:
            return {"error": "not_found", "message": "Appointment not found."}
        return {
            "appointment_id": result.appointment_id,
            "new_date": str(result.date),
            "new_time_slot": result.time_slot,
            "status": result.status,
        }

    async def _get_patient_appointments(self, patient_id: str) -> dict:
        appts = await self.engine.list_by_patient(patient_id)
        return {"patient_id": patient_id, "appointments": appts}
