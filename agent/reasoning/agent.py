"""
Voice Agent — LLM-powered reasoning + tool orchestration.

Flow:
  user_text → build_prompt (with memory) → LLM → parse intent →
  tool call → format response → update session memory
"""

import json
import logging
import os
import time
from typing import Optional

import httpx

from agent.prompt.templates import build_system_prompt, build_campaign_prompt
from agent.tools.appointment_tools import AppointmentTools
from backend.api.models import AgentIntent
from memory.session_memory.session_store import SessionStore
from memory.persistent_memory.patient_store import PatientStore
from scheduler.appointment_engine.engine import AppointmentEngine

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")  # "anthropic" | "openai"
MODEL_NAME = os.getenv("LLM_MODEL", "claude-3-5-haiku-20241022")


class VoiceAgent:
    def __init__(
        self,
        session_store: SessionStore,
        patient_store: PatientStore,
        appointment_engine: AppointmentEngine,
    ):
        self.session_store = session_store
        self.patient_store = patient_store
        self.appointment_engine = appointment_engine
        self.tools = AppointmentTools(appointment_engine)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def process(
        self,
        session_id: str,
        patient_id: Optional[str],
        user_text: str,
        language: str,
    ) -> dict:
        """
        Process a user utterance and return an agent response dict:
        {
          "text": str,         # spoken response
          "language": str,     # response language
          "intent": str,       # detected intent
          "tool_calls": list,  # tools invoked
        }
        """
        # Load session + persistent context
        session = await self.session_store.get_session(session_id) or {}
        patient = (await self.patient_store.get_patient(patient_id) or {}) if patient_id else {}

        # Persist detected language
        if language and language != "unknown":
            session["language"] = language
            if patient_id:
                await self.patient_store.update_language_preference(patient_id, language)

        # Build conversation history for LLM
        history = session.get("history", [])
        system_prompt = build_system_prompt(language, patient)

        messages = history + [{"role": "user", "content": user_text}]

        # Call LLM with tool definitions
        llm_response = await self._call_llm(system_prompt, messages)

        # Parse intent + tool calls from LLM response
        result = await self._execute_response(llm_response, language, session, patient_id)

        # Update session history (keep last 10 turns for context window)
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": result["text"]})
        session["history"] = history[-20:]  # 10 turns * 2 roles
        session["last_intent"] = result.get("intent")
        await self.session_store.update_session(session_id, session)

        return result

    # ------------------------------------------------------------------
    # LLM call (Anthropic Claude or OpenAI)
    # ------------------------------------------------------------------

    async def _call_llm(self, system_prompt: str, messages: list) -> dict:
        if LLM_PROVIDER == "anthropic":
            return await self._call_anthropic(system_prompt, messages)
        return await self._call_openai(system_prompt, messages)

    async def _call_anthropic(self, system_prompt: str, messages: list) -> dict:
        tool_definitions = self.tools.get_tool_definitions()
        payload = {
            "model": MODEL_NAME,
            "max_tokens": 512,
            "system": system_prompt,
            "messages": messages,
            "tools": tool_definitions,
        }
        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def _call_openai(self, system_prompt: str, messages: list) -> dict:
        tool_definitions = self.tools.get_openai_tool_definitions()
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        payload = {
            "model": "gpt-4o-mini",
            "messages": full_messages,
            "tools": tool_definitions,
            "max_tokens": 512,
        }
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Parse LLM response and execute any tool calls
    # ------------------------------------------------------------------

    async def _execute_response(
        self, llm_response: dict, language: str, session: dict, patient_id: Optional[str]
    ) -> dict:
        tool_calls_made = []

        if LLM_PROVIDER == "anthropic":
            content_blocks = llm_response.get("content", [])
            text_parts = []
            for block in content_blocks:
                if block.get("type") == "text":
                    text_parts.append(block["text"])
                elif block.get("type") == "tool_use":
                    tool_name = block["name"]
                    tool_input = block.get("input", {})
                    tool_result = await self.tools.execute(tool_name, tool_input)
                    tool_calls_made.append({"tool": tool_name, "result": tool_result})
                    # Build a natural language summary for follow-up
                    text_parts.append(
                        await self._tool_result_to_speech(tool_name, tool_result, language, session, patient_id)
                    )
            final_text = " ".join(t for t in text_parts if t).strip()
        else:
            # OpenAI format
            choice = llm_response["choices"][0]["message"]
            final_text = choice.get("content") or ""
            if choice.get("tool_calls"):
                for tc in choice["tool_calls"]:
                    fn_name = tc["function"]["name"]
                    fn_args = json.loads(tc["function"]["arguments"])
                    tool_result = await self.tools.execute(fn_name, fn_args)
                    tool_calls_made.append({"tool": fn_name, "result": tool_result})
                    speech = await self._tool_result_to_speech(fn_name, tool_result, language, session, patient_id)
                    final_text += " " + speech

        if not final_text:
            final_text = _fallback_message(language)

        return {
            "text": final_text.strip(),
            "language": language,
            "intent": session.get("last_intent", "unknown"),
            "tool_calls": tool_calls_made,
        }

    async def _tool_result_to_speech(
        self, tool_name: str, result: dict, language: str, session: dict, patient_id: Optional[str]
    ) -> str:
        """Convert a tool result into a natural spoken response using LLM."""
        if result.get("error"):
            return _error_message(result["error"], language)

        # Use a lightweight LLM call to verbalize the tool result
        verbalizer_prompt = (
            f"You are a healthcare voice assistant. Verbalize this tool result naturally in {language}. "
            f"Be concise (1-2 sentences). Tool: {tool_name}. Result: {json.dumps(result)}"
        )
        try:
            resp = await self._call_llm(
                system_prompt=verbalizer_prompt,
                messages=[{"role": "user", "content": "Summarize the result naturally."}],
            )
            if LLM_PROVIDER == "anthropic":
                return resp["content"][0]["text"]
            return resp["choices"][0]["message"]["content"]
        except Exception:
            return json.dumps(result)

    # ------------------------------------------------------------------
    # Outbound campaign opening
    # ------------------------------------------------------------------

    async def get_campaign_opening(
        self, patient_id: Optional[str], campaign_id: Optional[str], session_id: str
    ) -> dict:
        patient = (await self.patient_store.get_patient(patient_id) or {}) if patient_id else {}
        lang = patient.get("preferred_language", "en")
        name = patient.get("name", "there")

        prompts = {
            "en": f"Hello {name}, this is your healthcare assistant from 2Care. I'm calling about your upcoming appointment. How can I help you today?",
            "hi": f"नमस्ते {name}, मैं 2Care से आपकी स्वास्थ्य सहायक बोल रही हूँ। मैं आपकी आगामी अपॉइंटमेंट के बारे में कॉल कर रही हूँ।",
            "ta": f"வணக்கம் {name}, நான் 2Care இலிருந்து உங்கள் சுகாதார உதவியாளர் பேசுகிறேன். உங்கள் வரவிருக்கும் அப்பாயின்ட்மென்ட் பற்றி அழைக்கிறேன்.",
        }
        text = prompts.get(lang, prompts["en"])

        await self.session_store.update_session(session_id, {
            "language": lang,
            "campaign_id": campaign_id,
            "patient_id": patient_id,
            "history": [{"role": "assistant", "content": text}],
        })
        return {"text": text, "language": lang}


# ------------------------------------------------------------------
# Utility helpers
# ------------------------------------------------------------------

def _fallback_message(language: str) -> str:
    msgs = {
        "en": "I'm sorry, I had trouble processing that. Could you please repeat?",
        "hi": "माफ़ करें, मुझे समझने में कठिनाई हुई। क्या आप दोबारा कह सकते हैं?",
        "ta": "மன்னிக்கவும், புரிந்துகொள்வதில் சிரமம் இருந்தது. மீண்டும் சொல்ல முடியுமா?",
    }
    return msgs.get(language, msgs["en"])


def _error_message(error: str, language: str) -> str:
    msgs = {
        "en": f"I encountered an issue: {error}. Please try again.",
        "hi": f"एक समस्या आई: {error}. कृपया पुनः प्रयास करें।",
        "ta": f"ஒரு சிக்கல் ஏற்பட்டது: {error}. மீண்டும் முயற்சிக்கவும்.",
    }
    return msgs.get(language, msgs["en"])
