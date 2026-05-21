"""
Prompt templates for the healthcare voice agent.
Carefully crafted to keep the LLM focused and low-latency.
"""

from datetime import date


def build_system_prompt(language: str, patient: dict) -> str:
    """
    Build the system prompt incorporating patient context and language.
    Kept deliberately concise to reduce token count → lower latency.
    """
    today = date.today().isoformat()
    name = patient.get("name", "the patient")
    preferred_doctor = patient.get("preferred_doctor", "")
    preferred_hospital = patient.get("preferred_hospital", "")
    past_appts = patient.get("past_appointments", [])
    last_appt = past_appts[-1] if past_appts else None

    lang_instruction = {
        "en": "Respond in English.",
        "hi": "हिंदी में जवाब दें। (Respond in Hindi.)",
        "ta": "தமிழில் பதில் சொல்லவும். (Respond in Tamil.)",
    }.get(language, "Respond in English.")

    patient_context = ""
    if name != "the patient":
        patient_context += f"\nPatient name: {name}"
    if preferred_doctor:
        patient_context += f"\nPreferred doctor: {preferred_doctor}"
    if preferred_hospital:
        patient_context += f"\nPreferred hospital: {preferred_hospital}"
    if last_appt:
        patient_context += f"\nLast appointment: {last_appt}"

    return f"""You are a helpful, empathetic voice assistant for 2Care, a digital healthcare platform.
Today's date: {today}
{lang_instruction}
{patient_context}

Your role:
- Help patients book, reschedule, or cancel clinical appointments
- Check doctor availability
- Handle conflicts and suggest alternatives
- Be warm, concise, and clear (you are speaking out loud — avoid markdown or lists)
- Always confirm critical details (date, time, doctor) before finalizing
- If the patient's request is unclear, ask ONE clarifying question

Use the available tools to perform real appointment actions. Never make up availability or confirmation details.
After tool results, verbalize them naturally as a helpful agent would speak — not as raw data.
"""


def build_campaign_prompt(campaign_type: str, language: str, patient: dict) -> str:
    """
    Prompt for outbound campaign calls.
    """
    name = patient.get("name", "there")
    today = date.today().isoformat()
    lang_instruction = {
        "en": "Respond in English.",
        "hi": "हिंदी में जवाब दें।",
        "ta": "தமிழில் பதில் சொல்லவும்.",
    }.get(language, "Respond in English.")

    campaign_context = {
        "reminder": f"You are calling {name} to remind them about an upcoming appointment.",
        "followup": f"You are calling {name} for a post-appointment follow-up check.",
        "vaccination": f"You are calling {name} about a vaccination reminder.",
    }.get(campaign_type, f"You are calling {name} for a healthcare outreach.")

    return f"""You are a proactive voice assistant from 2Care healthcare.
Today's date: {today}
{lang_instruction}
{campaign_context}

Be polite, warm, and brief. You initiated this call. If the patient wants to book, reschedule, or cancel, use the tools available.
Adapt naturally to whatever the patient says — do not follow a rigid script.
"""
