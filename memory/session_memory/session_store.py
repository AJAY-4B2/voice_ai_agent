"""
Session Memory Store — Redis-backed, per-conversation context.

Stores:
  - Current conversation history (last N turns)
  - Pending intent / partial booking state
  - Detected language for this session
  - Session metadata

TTL: 2 hours (configurable). Sessions expire automatically.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

SESSION_TTL_SECONDS = int(60 * 60 * 2)  # 2 hours
SESSION_KEY_PREFIX = "session:"


class SessionStore:
    def __init__(self, redis):
        self.redis = redis

    def _key(self, session_id: str) -> str:
        return f"{SESSION_KEY_PREFIX}{session_id}"

    async def create_session(self, session_id: str, patient_id: Optional[str] = None) -> dict:
        """Initialize a new session. Safe to call if session already exists."""
        existing = await self.get_session(session_id)
        if existing:
            return existing
        session = {
            "session_id": session_id,
            "patient_id": patient_id,
            "language": None,
            "history": [],
            "last_intent": None,
            "pending_booking": None,
        }
        await self.redis.setex(self._key(session_id), SESSION_TTL_SECONDS, json.dumps(session))
        logger.info(f"Session created: {session_id}")
        return session

    async def get_session(self, session_id: str) -> Optional[dict]:
        raw = await self.redis.get(self._key(session_id))
        if not raw:
            return None
        return json.loads(raw)

    async def update_session(self, session_id: str, updates: dict) -> dict:
        """Merge updates into session and reset TTL."""
        session = await self.get_session(session_id) or {}
        session.update(updates)
        await self.redis.setex(self._key(session_id), SESSION_TTL_SECONDS, json.dumps(session))
        return session

    async def close_session(self, session_id: str):
        """Mark session as closed. Does NOT delete — preserved for analytics."""
        await self.update_session(session_id, {"closed": True})
        logger.info(f"Session closed: {session_id}")

    async def delete_session(self, session_id: str):
        await self.redis.delete(self._key(session_id))

    async def get_pending_booking(self, session_id: str) -> Optional[dict]:
        session = await self.get_session(session_id)
        return session.get("pending_booking") if session else None

    async def set_pending_booking(self, session_id: str, booking: dict):
        await self.update_session(session_id, {"pending_booking": booking})

    async def clear_pending_booking(self, session_id: str):
        await self.update_session(session_id, {"pending_booking": None})
