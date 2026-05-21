"""
Outbound Campaign API.
Schedule and manage outbound reminder / follow-up campaigns.
"""

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from backend.api.models import CampaignRequest

router = APIRouter()


@router.post("/schedule")
async def schedule_campaign(
    req: CampaignRequest,
    background_tasks: BackgroundTasks,
    request: Request,
):
    """
    Schedule an outbound campaign.
    The scheduler picks this up and initiates WebSocket calls to patients.
    """
    scheduler = request.app.state.appointment_engine  # reuse engine for simplicity
    # In production, push to background queue (Celery / BullMQ)
    background_tasks.add_task(_run_campaign, req, request.app.state)
    return {
        "status": "scheduled",
        "campaign_id": req.campaign_id,
        "patient_count": len(req.patient_ids),
    }


@router.get("/{campaign_id}/status")
async def campaign_status(campaign_id: str, request: Request):
    redis = request.app.state.redis
    data = await redis.get(f"campaign:{campaign_id}:status")
    if not data:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    import json
    return json.loads(data)


async def _run_campaign(req: CampaignRequest, app_state):
    """
    Background task: iterate over patients and trigger outbound calls.
    In production this would dispatch to a job queue and trigger
    WebRTC/Twilio/SIP calls per patient.
    """
    import json, asyncio
    redis = app_state.redis
    patient_store = app_state.patient_store
    tts_service = app_state.tts_service

    results = []
    for pid in req.patient_ids:
        patient = await patient_store.get_patient(pid)
        lang = req.language or (patient.get("preferred_language") if patient else "en") or "en"

        # Render message for this patient
        name = patient.get("name", "Patient") if patient else "Patient"
        text = req.message_template.replace("{name}", name)

        # In a real deployment: initiate outbound SIP/WebRTC call here
        # For demo: synthesize audio and mark as dispatched
        try:
            _audio = await tts_service.synthesize(text, lang)
            results.append({"patient_id": pid, "status": "dispatched", "language": lang})
        except Exception as e:
            results.append({"patient_id": pid, "status": "failed", "error": str(e)})

        await asyncio.sleep(0.1)  # rate limit

    status = {"campaign_id": req.campaign_id, "results": results, "total": len(results)}
    await redis.setex(f"campaign:{req.campaign_id}:status", 86400, json.dumps(status))
