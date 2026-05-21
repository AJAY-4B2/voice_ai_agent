"""
Appointments REST API router.
Provides endpoints for booking, rescheduling, cancellation, and availability.
"""

from datetime import date
from fastapi import APIRouter, Request, HTTPException
from backend.api.models import (
    AppointmentRequest, AppointmentResponse,
    RescheduleRequest, CancelRequest,
    AvailabilityRequest, AvailabilityResponse,
)

router = APIRouter()


@router.post("/book", response_model=AppointmentResponse)
async def book_appointment(req: AppointmentRequest, request: Request):
    engine = request.app.state.appointment_engine
    result = await engine.book(req)
    if not result:
        raise HTTPException(status_code=409, detail="Slot unavailable or conflict detected.")
    return result


@router.post("/reschedule", response_model=AppointmentResponse)
async def reschedule_appointment(req: RescheduleRequest, request: Request):
    engine = request.app.state.appointment_engine
    result = await engine.reschedule(req)
    if not result:
        raise HTTPException(status_code=404, detail="Appointment not found.")
    return result


@router.post("/cancel")
async def cancel_appointment(req: CancelRequest, request: Request):
    engine = request.app.state.appointment_engine
    ok = await engine.cancel(req)
    if not ok:
        raise HTTPException(status_code=404, detail="Appointment not found.")
    return {"status": "cancelled", "appointment_id": req.appointment_id}


@router.get("/availability", response_model=AvailabilityResponse)
async def get_availability(doctor_id: str, date: date, request: Request):
    engine = request.app.state.appointment_engine
    return await engine.get_availability(doctor_id, date)


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(appointment_id: str, request: Request):
    engine = request.app.state.appointment_engine
    appt = await engine.get(appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Not found.")
    return appt


@router.get("/patient/{patient_id}")
async def list_patient_appointments(patient_id: str, request: Request):
    engine = request.app.state.appointment_engine
    return await engine.list_by_patient(patient_id)
