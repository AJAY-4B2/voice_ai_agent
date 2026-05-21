"""
Comprehensive test suite for Voice AI Agent.

Tests:
- Appointment booking, rescheduling, cancellation
- Conflict detection
- Language detection
- Session memory
- Agent intent parsing
- Latency targets (mocked)
- Outbound campaign
"""

import asyncio
import json
import pytest
import sys
import os
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scheduler.appointment_engine.engine import AppointmentEngine
from services.language_detection.detector import LanguageDetector
from backend.api.models import AppointmentRequest, RescheduleRequest, CancelRequest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    return AppointmentEngine()


@pytest.fixture
def language_detector():
    return LanguageDetector()


def tomorrow() -> date:
    return date.today() + timedelta(days=1)


def next_week() -> date:
    return date.today() + timedelta(days=7)


# ---------------------------------------------------------------------------
# 1. Appointment Booking
# ---------------------------------------------------------------------------

class TestAppointmentBooking:

    @pytest.mark.asyncio
    async def test_book_appointment_success(self, engine):
        req = AppointmentRequest(
            patient_id="p001",
            doctor_id="doc_001",
            date=tomorrow(),
            time_slot="10:00",
        )
        result = await engine.book(req)
        assert result is not None
        assert result.status == "confirmed"
        assert result.appointment_id is not None
        assert result.doctor_name == "Dr. Arjun Sharma"
        print(f"✅ Booked: {result.appointment_id}")

    @pytest.mark.asyncio
    async def test_book_by_specialty(self, engine):
        """Should resolve 'cardiologist' to the correct doctor."""
        req = AppointmentRequest(
            patient_id="p001",
            doctor_id="cardiologist",
            date=tomorrow(),
            time_slot="11:00",
        )
        result = await engine.book(req)
        assert result is not None
        assert "Sharma" in result.doctor_name or result.doctor_id == "doc_001"
        print(f"✅ Specialty booking: {result.doctor_name}")

    @pytest.mark.asyncio
    async def test_book_conflict_same_slot(self, engine):
        """Second booking on same slot must be rejected."""
        req = AppointmentRequest(
            patient_id="p001", doctor_id="doc_002", date=tomorrow(), time_slot="14:00"
        )
        first = await engine.book(req)
        assert first is not None

        req2 = AppointmentRequest(
            patient_id="p002", doctor_id="doc_002", date=tomorrow(), time_slot="14:00"
        )
        conflict = await engine.book(req2)
        assert conflict is None
        print("✅ Conflict detection: double-booking correctly rejected")

    @pytest.mark.asyncio
    async def test_book_past_time_rejected(self, engine):
        """Booking a slot in the past must be rejected."""
        past_date = date.today() - timedelta(days=1)
        req = AppointmentRequest(
            patient_id="p001", doctor_id="doc_003", date=past_date, time_slot="10:00"
        )
        result = await engine.book(req)
        assert result is None
        print("✅ Past-time booking correctly rejected")

    @pytest.mark.asyncio
    async def test_book_unknown_doctor_rejected(self, engine):
        """Unknown doctor ID must be rejected."""
        req = AppointmentRequest(
            patient_id="p001", doctor_id="doc_999", date=tomorrow(), time_slot="10:00"
        )
        result = await engine.book(req)
        assert result is None
        print("✅ Unknown doctor correctly rejected")


# ---------------------------------------------------------------------------
# 2. Rescheduling
# ---------------------------------------------------------------------------

class TestRescheduling:

    @pytest.mark.asyncio
    async def test_reschedule_success(self, engine):
        req = AppointmentRequest(
            patient_id="p001", doctor_id="doc_001", date=tomorrow(), time_slot="09:00"
        )
        appt = await engine.book(req)
        assert appt is not None

        reschedule_req = RescheduleRequest(
            appointment_id=appt.appointment_id,
            new_date=next_week(),
            new_time_slot="15:00",
        )
        result = await engine.reschedule(reschedule_req)
        assert result is not None
        assert result.status == "rescheduled"
        assert str(result.date) == str(next_week())
        assert result.time_slot == "15:00"
        print(f"✅ Rescheduled to {result.date} {result.time_slot}")

    @pytest.mark.asyncio
    async def test_reschedule_not_found(self, engine):
        req = RescheduleRequest(
            appointment_id="NONEXISTENT",
            new_date=next_week(),
            new_time_slot="10:00",
        )
        result = await engine.reschedule(req)
        assert result is None
        print("✅ Reschedule of nonexistent appointment correctly returns None")

    @pytest.mark.asyncio
    async def test_reschedule_to_conflicting_slot(self, engine):
        """Can't reschedule into an already-booked slot."""
        r1 = AppointmentRequest(patient_id="p001", doctor_id="doc_004", date=next_week(), time_slot="10:00")
        r2 = AppointmentRequest(patient_id="p002", doctor_id="doc_004", date=next_week(), time_slot="11:00")

        a1 = await engine.book(r1)
        a2 = await engine.book(r2)
        assert a1 and a2

        # Try to reschedule a2 into a1's slot
        rr = RescheduleRequest(
            appointment_id=a2.appointment_id,
            new_date=next_week(),
            new_time_slot="10:00",
        )
        result = await engine.reschedule(rr)
        assert result is None
        print("✅ Reschedule into occupied slot correctly rejected")


# ---------------------------------------------------------------------------
# 3. Cancellation
# ---------------------------------------------------------------------------

class TestCancellation:

    @pytest.mark.asyncio
    async def test_cancel_success(self, engine):
        req = AppointmentRequest(
            patient_id="p001", doctor_id="doc_005", date=tomorrow(), time_slot="09:30"
        )
        appt = await engine.book(req)
        assert appt is not None

        cancel_req = CancelRequest(appointment_id=appt.appointment_id)
        ok = await engine.cancel(cancel_req)
        assert ok is True

        # Slot should now be free
        new_booking = await engine.book(AppointmentRequest(
            patient_id="p002", doctor_id="doc_005", date=tomorrow(), time_slot="09:30"
        ))
        assert new_booking is not None
        print("✅ Cancelled and slot freed correctly")

    @pytest.mark.asyncio
    async def test_cancel_nonexistent(self, engine):
        cancel_req = CancelRequest(appointment_id="FAKE_ID")
        ok = await engine.cancel(cancel_req)
        assert ok is False
        print("✅ Cancel nonexistent correctly returns False")


# ---------------------------------------------------------------------------
# 4. Availability
# ---------------------------------------------------------------------------

class TestAvailability:

    @pytest.mark.asyncio
    async def test_availability_returns_slots(self, engine):
        result = await engine.get_availability("doc_001", tomorrow())
        assert len(result["available_slots"]) > 0
        print(f"✅ Availability slots: {result['available_slots']}")

    @pytest.mark.asyncio
    async def test_availability_excludes_booked(self, engine):
        req = AppointmentRequest(
            patient_id="p001", doctor_id="doc_002", date=next_week(), time_slot="09:00"
        )
        await engine.book(req)

        result = await engine.get_availability("doc_002", next_week())
        assert "09:00" not in result["available_slots"]
        print("✅ Booked slot excluded from availability")

    @pytest.mark.asyncio
    async def test_availability_by_specialty(self, engine):
        result = await engine.get_availability_by_id_or_specialty("dermatologist", str(tomorrow()))
        assert result is not None
        assert result["doctor_id"] == "doc_002"
        print(f"✅ Specialty resolved: {result['doctor_name']}")


# ---------------------------------------------------------------------------
# 5. Language Detection
# ---------------------------------------------------------------------------

class TestLanguageDetection:

    @pytest.mark.asyncio
    async def test_detect_english(self, language_detector):
        lang = await language_detector.detect("Book appointment with cardiologist tomorrow")
        assert lang == "en"
        print(f"✅ English detected: {lang}")

    @pytest.mark.asyncio
    async def test_detect_hindi(self, language_detector):
        lang = await language_detector.detect("मुझे कल डॉक्टर से मिलना है")
        assert lang == "hi"
        print(f"✅ Hindi detected: {lang}")

    @pytest.mark.asyncio
    async def test_detect_tamil(self, language_detector):
        lang = await language_detector.detect("நாளை மருத்துவரை பார்க்க வேண்டும்")
        assert lang == "ta"
        print(f"✅ Tamil detected: {lang}")

    @pytest.mark.asyncio
    async def test_detect_empty(self, language_detector):
        lang = await language_detector.detect("")
        assert lang == "unknown"
        print("✅ Empty string → unknown")

    @pytest.mark.asyncio
    async def test_detect_hindi_mixed(self, language_detector):
        lang = await language_detector.detect("Please मुझे appointment chahiye")
        assert lang == "hi"
        print("✅ Mixed Hindi/English correctly detected as Hindi")


# ---------------------------------------------------------------------------
# 6. Session Memory
# ---------------------------------------------------------------------------

class TestSessionMemory:

    @pytest.mark.asyncio
    async def test_session_create_and_retrieve(self):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_redis.setex = AsyncMock()

        from memory.session_memory.session_store import SessionStore
        store = SessionStore(mock_redis)

        session = await store.create_session("sess_001", "patient_001")
        assert session["session_id"] == "sess_001"
        assert session["patient_id"] == "patient_001"
        assert session["history"] == []
        print("✅ Session created with correct defaults")

    @pytest.mark.asyncio
    async def test_session_update(self):
        import json
        stored = {}

        mock_redis = AsyncMock()
        mock_redis.get.side_effect = lambda key: stored.get(key)
        async def mock_setex(key, ttl, val):
            stored[key] = val
        mock_redis.setex.side_effect = mock_setex

        from memory.session_memory.session_store import SessionStore
        store = SessionStore(mock_redis)

        await store.create_session("sess_002")
        stored_raw = stored.get("session:sess_002")
        assert stored_raw is not None

        await store.update_session("sess_002", {"language": "hi"})
        updated = json.loads(stored.get("session:sess_002"))
        assert updated["language"] == "hi"
        print("✅ Session update persisted correctly")


# ---------------------------------------------------------------------------
# 7. Latency Measurement
# ---------------------------------------------------------------------------

class TestLatencyTarget:

    @pytest.mark.asyncio
    async def test_appointment_engine_sub_50ms(self, engine):
        """Booking operation must complete in under 50ms."""
        import time
        req = AppointmentRequest(
            patient_id="p_lat", doctor_id="doc_001", date=next_week(), time_slot="16:00"
        )
        t0 = time.monotonic()
        result = await engine.book(req)
        elapsed_ms = (time.monotonic() - t0) * 1000
        assert result is not None
        assert elapsed_ms < 50
        print(f"✅ Booking engine latency: {elapsed_ms:.1f}ms (< 50ms)")

    @pytest.mark.asyncio
    async def test_language_detection_sub_5ms(self, language_detector):
        import time
        texts = [
            "Book appointment with doctor",
            "मुझे डॉक्टर से मिलना है",
            "நாளை மருத்துவரை பார்க்க",
        ]
        for text in texts:
            t0 = time.monotonic()
            await language_detector.detect(text)
            elapsed_ms = (time.monotonic() - t0) * 1000
            assert elapsed_ms < 5
            print(f"✅ Language detection: {elapsed_ms:.2f}ms (< 5ms)")


# ---------------------------------------------------------------------------
# 8. Tool Orchestration
# ---------------------------------------------------------------------------

class TestToolOrchestration:

    @pytest.mark.asyncio
    async def test_check_availability_tool(self):
        engine = AppointmentEngine()
        from agent.tools.appointment_tools import AppointmentTools
        tools = AppointmentTools(engine)

        result = await tools.execute("check_availability", {
            "doctor_id": "cardiologist",
            "date": str(tomorrow()),
        })
        assert "available_slots" in result
        assert len(result["available_slots"]) > 0
        print(f"✅ check_availability tool: {len(result['available_slots'])} slots")

    @pytest.mark.asyncio
    async def test_book_appointment_tool(self):
        engine = AppointmentEngine()
        from agent.tools.appointment_tools import AppointmentTools
        tools = AppointmentTools(engine)

        result = await tools.execute("book_appointment", {
            "patient_id": "p001",
            "doctor_id": "doc_003",
            "date": str(tomorrow()),
            "time_slot": "10:30",
        })
        assert "appointment_id" in result
        assert result["status"] == "confirmed"
        print(f"✅ book_appointment tool: {result['appointment_id']}")

    @pytest.mark.asyncio
    async def test_cancel_appointment_tool(self):
        engine = AppointmentEngine()
        from agent.tools.appointment_tools import AppointmentTools
        tools = AppointmentTools(engine)

        book_result = await tools.execute("book_appointment", {
            "patient_id": "p001",
            "doctor_id": "doc_004",
            "date": str(tomorrow()),
            "time_slot": "15:30",
        })
        assert "appointment_id" in book_result

        cancel_result = await tools.execute("cancel_appointment", {
            "appointment_id": book_result["appointment_id"],
        })
        assert cancel_result["status"] == "cancelled"
        print(f"✅ cancel_appointment tool: {cancel_result['appointment_id']}")

    @pytest.mark.asyncio
    async def test_reschedule_tool(self):
        engine = AppointmentEngine()
        from agent.tools.appointment_tools import AppointmentTools
        tools = AppointmentTools(engine)

        book_result = await tools.execute("book_appointment", {
            "patient_id": "p001",
            "doctor_id": "doc_005",
            "date": str(tomorrow()),
            "time_slot": "14:30",
        })
        assert "appointment_id" in book_result

        rr = await tools.execute("reschedule_appointment", {
            "appointment_id": book_result["appointment_id"],
            "new_date": str(next_week()),
            "new_time_slot": "11:00",
        })
        assert rr["status"] == "rescheduled"
        assert rr["new_time_slot"] == "11:00"
        print(f"✅ reschedule_appointment tool successful")


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-p", "no:warnings"])
