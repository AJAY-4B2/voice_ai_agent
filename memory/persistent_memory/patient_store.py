"""
Persistent Patient Memory Store — Redis-backed, cross-session patient context.

Stores long-term patient preferences and history:
  - preferred_language
  - preferred_doctor
  - preferred_hospital
  - past_appointments (last 20)
  - name, phone, etc.

TTL: 90 days. Refreshed on each access.
"""

import json
import logging
from datetime import datetime
from typing import Optional, List

logger = logging.getLogger(__name__)

PATIENT_TTL_SECONDS = 90 * 24 * 60 * 60  # 90 days
PATIENT_KEY_PREFIX = "patient:"


class PatientStore:
    def __init__(self, redis):
        self.redis = redis

    def _key(self, patient_id: str) -> str:
        return f"{PATIENT_KEY_PREFIX}{patient_id}"

    async def get_patient(self, patient_id: str) -> Optional[dict]:
        raw = await self.redis.get(self._key(patient_id))
        if not raw:
            return None
        data = json.loads(raw)
        # Refresh TTL on access
        await self.redis.expire(self._key(patient_id), PATIENT_TTL_SECONDS)
        return data

    async def upsert_patient(self, patient_id: str, data: dict) -> dict:
        existing = await self.get_patient(patient_id) or {}
        existing.update(data)
        existing["patient_id"] = patient_id
        existing["updated_at"] = datetime.utcnow().isoformat()
        await self.redis.setex(self._key(patient_id), PATIENT_TTL_SECONDS, json.dumps(existing))
        return existing

    async def update_language_preference(self, patient_id: str, language: str):
        await self.upsert_patient(patient_id, {"preferred_language": language})
        logger.info(f"Patient {patient_id} language preference set to {language}")

    async def add_appointment_to_history(self, patient_id: str, appointment: dict):
        """Keep last 20 appointments in patient history."""
        patient = await self.get_patient(patient_id) or {}
        history = patient.get("past_appointments", [])
        history.append({**appointment, "recorded_at": datetime.utcnow().isoformat()})
        history = history[-20:]
        await self.upsert_patient(patient_id, {"past_appointments": history})

    async def get_appointment_history(self, patient_id: str) -> List[dict]:
        patient = await self.get_patient(patient_id) or {}
        return patient.get("past_appointments", [])

    async def delete_patient(self, patient_id: str):
        await self.redis.delete(self._key(patient_id))
