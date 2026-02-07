"""FastAPI prototype for Room Companion — nursing home AI assistant.

Features:
- LLM-powered conversational chat per room
- Intent classification with severity levels
- Real-time alert management for staff
- Multi-room support with resident profiles
- Voice input/output (handled client-side)
"""

import asyncio
from datetime import datetime
import datetime as dt
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import sqlite3

from llm import load_api_keys, chat, classify, get_greeting, ClassificationResult

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "alerts.db"

app = FastAPI(title="Room Companion")

# Static files & templates
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ==========================
# Database helpers
# ==========================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id TEXT NOT NULL,
            resident_name TEXT NOT NULL,
            type TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            severity TEXT NOT NULL DEFAULT 'routine',
            created_at TEXT NOT NULL,
            acknowledged_at TEXT,
            resolved_at TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id TEXT NOT NULL,
            resident_name TEXT NOT NULL,
            question TEXT NOT NULL,
            response TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    # Migration: add severity column if missing (existing DBs)
    cursor.execute("PRAGMA table_info(alerts)")
    columns = [row[1] for row in cursor.fetchall()]
    if "severity" not in columns:
        cursor.execute("ALTER TABLE alerts ADD COLUMN severity TEXT NOT NULL DEFAULT 'routine'")

    # Migration: add response column to questions if missing
    cursor.execute("PRAGMA table_info(questions)")
    columns = [row[1] for row in cursor.fetchall()]
    if "response" not in columns:
        cursor.execute("ALTER TABLE questions ADD COLUMN response TEXT")

    conn.commit()
    conn.close()


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# Run at startup
init_db()
load_api_keys()


# ==========================
# API models
# ==========================

class AlertCreate(BaseModel):
    room_id: str
    resident_name: str
    type: str
    message: str
    severity: str = "routine"
    timestamp: Optional[str] = None


class Alert(BaseModel):
    id: int
    room_id: str
    resident_name: str
    type: str
    message: str
    status: str
    severity: str
    created_at: str
    acknowledged_at: Optional[str]
    resolved_at: Optional[str]


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    alert_created: bool
    severity: Optional[str] = None


class TTSRequest(BaseModel):
    text: str
    mode: str = "standard"


# ==========================
# Resident profiles
# ==========================

RESIDENT_PROFILES = {
    "101": {
        "resident_name": "Margaret",
        "mode": "standard",
    },
    "102": {
        "resident_name": "Harold",
        "mode": "memory_support",
    },
    "103": {
        "resident_name": "Dorothy",
        "mode": "standard",
    },
}


# ==========================
# API endpoints
# ==========================

@app.post("/api/alerts", response_model=Alert)
def create_alert(alert: AlertCreate):
    """Create a new alert."""
    now_str = alert.timestamp or datetime.utcnow().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO alerts
               (room_id, resident_name, type, message, status, severity, created_at)
               VALUES (?, ?, ?, ?, 'new', ?, ?)""",
        (alert.room_id, alert.resident_name, alert.type, alert.message, alert.severity, now_str),
    )
    conn.commit()
    alert_id = cursor.lastrowid
    cursor.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
    row = cursor.fetchone()
    conn.close()
    return Alert(**dict(row))


@app.get("/api/alerts", response_model=List[Alert])
def list_alerts(status: Optional[str] = None, room_id: Optional[str] = None):
    """List alerts, optionally filtered by status or room."""
    conn = get_db_connection()
    cursor = conn.cursor()
    conditions = []
    params = []
    if status:
        conditions.append("status = ?")
        params.append(status)
    if room_id:
        conditions.append("room_id = ?")
        params.append(room_id)
    where = " AND ".join(conditions)
    query = "SELECT * FROM alerts"
    if where:
        query += f" WHERE {where}"
    query += " ORDER BY created_at DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [Alert(**dict(row)) for row in rows]


@app.post("/api/alerts/{alert_id}/ack", response_model=Alert)
def acknowledge_alert(alert_id: int):
    """Mark an alert as acknowledged."""
    now_str = datetime.utcnow().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE alerts SET status = 'ack', acknowledged_at = ?
           WHERE id = ? AND status = 'new'""",
        (now_str, alert_id),
    )
    conn.commit()
    cursor.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
    row = cursor.fetchone()
    conn.close()
    return Alert(**dict(row))


@app.post("/api/alerts/{alert_id}/resolve", response_model=Alert)
def resolve_alert(alert_id: int):
    """Mark an alert as resolved."""
    now_str = datetime.utcnow().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE alerts SET status = 'resolved', resolved_at = ?
           WHERE id = ?""",
        (now_str, alert_id),
    )
    conn.commit()
    cursor.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
    row = cursor.fetchone()
    conn.close()
    return Alert(**dict(row))


@app.get("/api/alerts/summary")
def alerts_summary():
    """Per-room summary: help counts (30m), orientation counts (7d), active alerts."""
    conn = get_db_connection()
    cursor = conn.cursor()
    summary = {}

    for room_id, profile in RESIDENT_PROFILES.items():
        # Help alert count (last 30 min)
        cursor.execute(
            """SELECT COUNT(*) FROM alerts
               WHERE room_id = ? AND type = 'help'
               AND datetime(created_at) >= datetime('now', '-30 minutes')""",
            (room_id,),
        )
        help_count = cursor.fetchone()[0]

        # Orientation question count (last 7 days)
        cursor.execute(
            """SELECT COUNT(*) FROM questions
               WHERE room_id = ?
               AND datetime(created_at) >= datetime('now', '-7 days')
               AND (lower(question) LIKE '%where am i%'
                    OR lower(question) LIKE '%what time%'
                    OR lower(question) LIKE '%what day%')""",
            (room_id,),
        )
        orientation_count = cursor.fetchone()[0]

        # Active (unresolved) alerts count
        cursor.execute(
            """SELECT COUNT(*) FROM alerts
               WHERE room_id = ? AND status != 'resolved'""",
            (room_id,),
        )
        active_count = cursor.fetchone()[0]

        # Most recent alert severity
        cursor.execute(
            """SELECT severity FROM alerts
               WHERE room_id = ? AND status != 'resolved'
               ORDER BY created_at DESC LIMIT 1""",
            (room_id,),
        )
        row = cursor.fetchone()
        latest_severity = row[0] if row else None

        summary[room_id] = {
            "resident_name": profile["resident_name"],
            "mode": profile["mode"],
            "help_count_30m": help_count,
            "orientation_count_7d": orientation_count,
            "active_alerts": active_count,
            "latest_severity": latest_severity,
        }

    conn.close()
    return summary


# ==========================
# Chat endpoint (LLM-powered)
# ==========================

@app.post("/api/room/{room_id}/chat", response_model=ChatResponse)
async def room_chat(room_id: str, req: ChatRequest):
    """Send a message to the Room Companion and get a response.

    Runs LLM chat and classification in parallel.
    Creates alert if classification detects a help request.
    """
    profile = RESIDENT_PROFILES.get(room_id)
    if not profile:
        return JSONResponse({"error": "Unknown room"}, status_code=404)

    resident_name = profile["resident_name"]
    mode = profile["mode"]
    user_message = req.message.strip()

    if not user_message:
        return ChatResponse(response="I didn't catch that. Could you say that again?", alert_created=False)

    # Run chat and classify in parallel
    chat_task = chat(room_id, resident_name, mode, user_message)
    classify_task = classify(user_message)
    response_text, classification = await asyncio.gather(chat_task, classify_task)

    # Log the question + response
    now_str = datetime.utcnow().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO questions (room_id, resident_name, question, response, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (room_id, resident_name, user_message, response_text, now_str),
    )

    # Create alert if help request detected
    alert_created = False
    severity = None
    if classification.is_help_request and classification.confidence >= 0.5 and classification.severity != "informational":
        severity = classification.severity
        cursor.execute(
            """INSERT INTO alerts
                   (room_id, resident_name, type, message, status, severity, created_at)
                   VALUES (?, ?, 'help', ?, 'new', ?, ?)""",
            (room_id, resident_name, f"[{classification.severity}] {user_message}", severity, now_str),
        )
        alert_created = True

    conn.commit()
    conn.close()

    return ChatResponse(response=response_text, alert_created=alert_created, severity=severity)


# ==========================
# TTS endpoint (server-side via edge-tts)
# ==========================

@app.post("/api/tts")
async def text_to_speech(req: TTSRequest):
    """Generate speech audio from text using Microsoft Edge TTS."""
    import edge_tts

    text = req.text.strip()
    if not text:
        return JSONResponse({"error": "No text"}, status_code=400)

    voice = "en-US-AriaNeural"
    rate = "-10%" if req.mode == "memory_support" else "+0%"

    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
    chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])

    return Response(content=b"".join(chunks), media_type="audio/mpeg")


# ==========================
# HTML views
# ==========================

@app.get("/room/{room_id}", response_class=HTMLResponse)
async def room_view(request: Request, room_id: str):
    """Room UI — resident-facing chat interface."""
    profile = RESIDENT_PROFILES.get(room_id)
    if not profile:
        return HTMLResponse(content=f"Unknown room: {room_id}", status_code=404)

    resident_name = profile["resident_name"]
    mode = profile["mode"]
    greeting = get_greeting(room_id, resident_name, mode)
    current_day = dt.datetime.now().strftime("%A")
    current_time = dt.datetime.now().strftime("%I:%M %p").lstrip("0")
    current_date = dt.datetime.now().strftime("%B %d, %Y")

    return templates.TemplateResponse(
        "room.html",
        {
            "request": request,
            "room_id": room_id,
            "resident_name": resident_name,
            "mode": mode,
            "greeting": greeting,
            "current_day": current_day,
            "current_time": current_time,
            "current_date": current_date,
        },
    )


@app.post("/room/{room_id}/help")
async def room_call_help(room_id: str, resident_name: str = Form(...)):
    """Handle 'Call for Help' button — creates emergency alert."""
    alert = AlertCreate(
        room_id=room_id,
        resident_name=resident_name,
        type="help",
        message="Resident requested help via button",
        severity="emergency",
    )
    create_alert(alert)
    return RedirectResponse(url=f"/room/{room_id}?helped=1", status_code=303)


@app.get("/staff", response_class=HTMLResponse)
async def staff_view(request: Request, room_id: Optional[str] = None, severity: Optional[str] = None, status: Optional[str] = None):
    """Staff portal — alert dashboard with room status cards."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Build filter query
    conditions = []
    params = []
    if room_id:
        conditions.append("room_id = ?")
        params.append(room_id)
    if severity:
        conditions.append("severity = ?")
        params.append(severity)
    if status:
        conditions.append("status = ?")
        params.append(status)

    where = " AND ".join(conditions)
    query = "SELECT * FROM alerts"
    if where:
        query += f" WHERE {where}"
    query += " ORDER BY created_at DESC LIMIT 100"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    # Room summary data
    room_help_counts = {}
    room_orientation_counts = {}
    room_active_alerts = {}
    room_latest_severity = {}

    for rid in RESIDENT_PROFILES.keys():
        cursor.execute(
            """SELECT COUNT(*) FROM alerts
               WHERE room_id = ? AND type = 'help'
               AND datetime(created_at) >= datetime('now', '-30 minutes')""",
            (rid,),
        )
        room_help_counts[rid] = cursor.fetchone()[0]

        cursor.execute(
            """SELECT COUNT(*) FROM questions
               WHERE room_id = ?
               AND datetime(created_at) >= datetime('now', '-7 days')
               AND (lower(question) LIKE '%where am i%'
                    OR lower(question) LIKE '%what time%'
                    OR lower(question) LIKE '%what day%')""",
            (rid,),
        )
        room_orientation_counts[rid] = cursor.fetchone()[0]

        cursor.execute(
            """SELECT COUNT(*) FROM alerts WHERE room_id = ? AND status != 'resolved'""",
            (rid,),
        )
        room_active_alerts[rid] = cursor.fetchone()[0]

        cursor.execute(
            """SELECT severity FROM alerts WHERE room_id = ? AND status != 'resolved'
               ORDER BY created_at DESC LIMIT 1""",
            (rid,),
        )
        sev_row = cursor.fetchone()
        room_latest_severity[rid] = sev_row[0] if sev_row else None

    conn.close()

    alerts = [dict(row) for row in rows]
    for alert in alerts:
        profile = RESIDENT_PROFILES.get(alert["room_id"], {})
        alert["mode"] = profile.get("mode", "standard")

    return templates.TemplateResponse(
        "staff.html", {
            "request": request,
            "alerts": alerts,
            "profiles": RESIDENT_PROFILES,
            "room_help_counts": room_help_counts,
            "room_orientation_counts": room_orientation_counts,
            "room_active_alerts": room_active_alerts,
            "room_latest_severity": room_latest_severity,
            "filter_room": room_id or "",
            "filter_severity": severity or "",
            "filter_status": status or "",
        }
    )


@app.post("/staff/alerts/{alert_id}/ack")
async def staff_ack_alert(alert_id: int):
    acknowledge_alert(alert_id)
    return RedirectResponse(url="/staff", status_code=303)


@app.post("/staff/alerts/{alert_id}/resolve")
async def staff_resolve_alert(alert_id: int):
    resolve_alert(alert_id)
    return RedirectResponse(url="/staff", status_code=303)


@app.get("/")
async def root():
    return RedirectResponse(url="/room/101")
