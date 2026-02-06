"""LLM integration layer for Room Companion.

Provides:
- Groq (primary) and OpenRouter (fallback) API calls
- Conversational chat with per-room history
- LLM-powered intent classification (help detection + severity)
- Canned fallback responses when both APIs fail
"""

import asyncio
import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------

GROQ_API_KEY: str = ""
OPENROUTER_API_KEY: str = ""

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

GROQ_MODEL = "llama-3.3-70b-versatile"
OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct:free"

TIMEOUT = 15.0  # seconds


def load_api_keys() -> None:
    """Read API keys from ~/.clawdbot/api-keys.env (shell export format)."""
    global GROQ_API_KEY, OPENROUTER_API_KEY
    env_path = Path.home() / ".clawdbot" / "api-keys.env"
    if not env_path.exists():
        print(f"[llm] Warning: {env_path} not found, LLM calls will fail")
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Handle export KEY="value" or KEY="value"
        line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        if key == "GROQ_API_KEY":
            GROQ_API_KEY = value
        elif key == "OPENROUTER_API_KEY":
            OPENROUTER_API_KEY = value
    loaded = []
    if GROQ_API_KEY:
        loaded.append("Groq")
    if OPENROUTER_API_KEY:
        loaded.append("OpenRouter")
    print(f"[llm] Loaded API keys: {', '.join(loaded) or 'none'}")


# ---------------------------------------------------------------------------
# Conversation history (in-memory, per room)
# ---------------------------------------------------------------------------

MAX_HISTORY = 20  # messages per room

_histories: dict[str, list[dict]] = defaultdict(list)


def _get_history(room_id: str) -> list[dict]:
    return _histories[room_id]


def _add_to_history(room_id: str, role: str, content: str) -> None:
    history = _histories[room_id]
    history.append({"role": role, "content": content})
    # Keep only the last MAX_HISTORY messages
    if len(history) > MAX_HISTORY:
        _histories[room_id] = history[-MAX_HISTORY:]


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

FACILITY_SCHEDULE = """Facility Schedule:
- Breakfast: 8:00 AM
- Morning activities: 9:30 AM
- Lunch: 12:00 PM
- Afternoon rest: 1:00 - 2:30 PM
- Afternoon activities: 3:00 PM
- Dinner: 5:30 PM
- Evening wind-down: 7:00 PM
- Lights optional by 9:00 PM"""


def build_system_prompt(room_id: str, resident_name: str, mode: str, current_time: str) -> str:
    """Build a two-layer system prompt: base identity + mode layer."""

    base = f"""You are the Room Companion, a friendly AI assistant in a nursing home facility.
You are located in Room {room_id}, assisting {resident_name}.
The current time is {current_time}.

Your role:
- Answer questions clearly and warmly in 2-3 sentences maximum.
- Help with orientation (time, date, schedule, location).
- If the resident seems distressed or asks for help, respond with calm reassurance and let them know staff are being notified.
- Never provide medical advice. For health concerns, say staff will be contacted.
- Be warm but not overly cheerful. Speak naturally, like a kind neighbor.

{FACILITY_SCHEDULE}

Safety rules:
- Never argue with or correct a confused resident harshly.
- If someone mentions falling, pain, or an emergency, respond with immediate reassurance.
- Do not discuss other residents or share any private information."""

    if mode == "memory_support":
        mode_layer = f"""

Mode: Memory Support
{resident_name} may experience confusion about time, place, or recent events.
- Always begin responses by gently orienting them: mention where they are, the time, or the day when relevant.
- Be patient with repeated questions — answer each time as if it's the first.
- Use simple, short sentences. Avoid complex explanations.
- Provide extra reassurance and comfort."""
    else:
        mode_layer = """

Mode: Standard
- Be direct and efficient in responses.
- The resident is generally oriented and independent.
- Keep answers helpful and concise."""

    return base + mode_layer


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

@dataclass
class ClassificationResult:
    is_help_request: bool
    severity: str  # emergency | urgent | routine | informational
    confidence: float
    explanation: str


CLASSIFY_PROMPT = """You are a safety classifier for a nursing home AI system.
Analyze the resident's message and determine if it's a help/distress request.

Respond ONLY with valid JSON (no markdown, no explanation outside JSON):
{
  "is_help_request": true/false,
  "severity": "emergency" | "urgent" | "routine" | "informational",
  "confidence": 0.0-1.0,
  "explanation": "brief reason"
}

Severity guide:
- emergency: immediate danger — falls, chest pain, can't breathe, unresponsive
- urgent: needs prompt attention — significant pain, feeling very unwell, can't reach something dangerous
- routine: non-urgent help — need bathroom assistance, medication reminder, general help request
- informational: not a help request — questions about schedule, chat, orientation questions

Message to classify: """


async def classify(user_message: str) -> ClassificationResult:
    """Classify a message for help intent and severity."""
    messages = [
        {"role": "user", "content": CLASSIFY_PROMPT + f'"{user_message}"'}
    ]
    try:
        raw = await _call_llm(messages, temperature=0.1)
        # Extract JSON from response
        raw = raw.strip()
        # Try to find JSON object in the response
        match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            data = json.loads(raw)
        return ClassificationResult(
            is_help_request=bool(data.get("is_help_request", False)),
            severity=data.get("severity", "informational"),
            confidence=float(data.get("confidence", 0.5)),
            explanation=data.get("explanation", ""),
        )
    except Exception as e:
        print(f"[llm] Classification failed: {e}, falling back to keyword detection")
        return _keyword_classify(user_message)


def _keyword_classify(text: str) -> ClassificationResult:
    """Fallback keyword-based classification when LLM fails."""
    lower = text.lower()
    emergency_words = ["fell", "fall", "can't breathe", "chest pain", "heart", "bleeding", "unconscious"]
    urgent_words = ["pain", "hurt", "sick", "dizzy", "nauseous"]
    help_words = ["help", "nurse", "someone", "assistance", "bathroom"]

    for word in emergency_words:
        if word in lower:
            return ClassificationResult(True, "emergency", 0.8, f"Keyword match: {word}")
    for word in urgent_words:
        if word in lower:
            return ClassificationResult(True, "urgent", 0.7, f"Keyword match: {word}")
    for word in help_words:
        if word in lower:
            return ClassificationResult(True, "routine", 0.6, f"Keyword match: {word}")
    return ClassificationResult(False, "informational", 0.9, "No distress keywords detected")


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

async def chat(room_id: str, resident_name: str, mode: str, user_message: str) -> str:
    """Generate a conversational response, maintaining per-room history."""
    now = datetime.now().strftime("%I:%M %p on %A, %B %d")
    system_prompt = build_system_prompt(room_id, resident_name, mode, now)

    _add_to_history(room_id, "user", user_message)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(_get_history(room_id))

    try:
        response = await _call_llm(messages, temperature=0.7)
        _add_to_history(room_id, "assistant", response)
        return response
    except Exception as e:
        print(f"[llm] Chat failed: {e}, using canned response")
        fallback = _canned_response(user_message, room_id, resident_name, mode)
        _add_to_history(room_id, "assistant", fallback)
        return fallback


def _canned_response(text: str, room_id: str, resident_name: str, mode: str) -> str:
    """Fallback canned responses when both APIs are down."""
    lower = text.lower()
    now = datetime.now()

    if "where am i" in lower or "what is this place" in lower:
        return f"You're in Room {room_id} at your care home, {resident_name}. You're safe here."
    if "time" in lower:
        return f"It's {now.strftime('%I:%M %p').lstrip('0')} right now."
    if "day" in lower or "date" in lower:
        return f"Today is {now.strftime('%A, %B %d')}."
    if "breakfast" in lower or "lunch" in lower or "dinner" in lower or "meal" in lower:
        return "Breakfast is at 8:00 AM, lunch at 12:00 PM, and dinner at 5:30 PM."
    if any(w in lower for w in ["help", "fell", "fall", "pain", "hurt"]):
        return "I'm letting the staff know right away. Help is on the way — please stay where you are."
    return "I'm having a little trouble right now, but the staff are always nearby if you need anything."


# ---------------------------------------------------------------------------
# LLM API caller (Groq primary, OpenRouter fallback)
# ---------------------------------------------------------------------------

async def _call_llm(messages: list[dict], temperature: float = 0.7) -> str:
    """Call Groq first, then OpenRouter if Groq fails. Raises on total failure."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Try Groq first
        if GROQ_API_KEY:
            try:
                resp = await client.post(
                    GROQ_URL,
                    headers={
                        "Authorization": f"Bearer {GROQ_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": GROQ_MODEL,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": 256,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                if content:
                    return content
            except Exception as e:
                print(f"[llm] Groq failed: {e}")

        # Fallback to OpenRouter
        if OPENROUTER_API_KEY:
            try:
                resp = await client.post(
                    OPENROUTER_URL,
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/Kidomigon/nursing-home-ai",
                        "X-Title": "Room Companion",
                    },
                    json={
                        "model": OPENROUTER_MODEL,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": 256,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                if content:
                    return content
            except Exception as e:
                print(f"[llm] OpenRouter failed: {e}")

    raise RuntimeError("Both Groq and OpenRouter failed")


# ---------------------------------------------------------------------------
# Greeting generation
# ---------------------------------------------------------------------------

def get_greeting(room_id: str, resident_name: str, mode: str) -> str:
    """Generate a deterministic greeting based on profile and time of day."""
    hour = datetime.now().hour
    if hour < 12:
        time_greeting = "Good morning"
    elif hour < 17:
        time_greeting = "Good afternoon"
    else:
        time_greeting = "Good evening"

    first_name = resident_name.split()[0]

    if mode == "memory_support":
        day = datetime.now().strftime("%A")
        time_str = datetime.now().strftime("%I:%M %p").lstrip("0")
        return (
            f"{time_greeting}, {first_name}. You're in Room {room_id} at your care home. "
            f"It's {day}, and the time is {time_str}. I'm here if you need anything."
        )
    else:
        return f"{time_greeting}, {first_name}. How can I help you today?"
