"""FastAPI prototype for Room Companion — nursing home AI assistant.

Features:
- LLM-powered conversational chat per room
- Intent classification with severity levels
- Real-time alert management for staff
- DB-driven multi-room support with resident profiles
- Staff authentication (shared PIN + name)
- Alert notes and attribution
- Voice input/output (handled client-side)
"""

import asyncio
import hashlib
import secrets
from datetime import datetime
import datetime as dt
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Request, Form, Cookie
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

# Staff PIN — SHA-256 hash of "1234" (change for production)
STAFF_PIN_HASH = hashlib.sha256("1234".encode()).hexdigest()
SESSION_EXPIRY_HOURS = 8


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

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS rooms (
            room_id TEXT PRIMARY KEY,
            resident_name TEXT NOT NULL,
            mode TEXT NOT NULL DEFAULT 'standard'
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            staff_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
        """
    )

    # Migration: add severity column if missing (existing DBs)
    cursor.execute("PRAGMA table_info(alerts)")
    columns = [row[1] for row in cursor.fetchall()]
    if "severity" not in columns:
        cursor.execute("ALTER TABLE alerts ADD COLUMN severity TEXT NOT NULL DEFAULT 'routine'")
    if "acknowledged_by" not in columns:
        cursor.execute("ALTER TABLE alerts ADD COLUMN acknowledged_by TEXT")
    if "resolved_by" not in columns:
        cursor.execute("ALTER TABLE alerts ADD COLUMN resolved_by TEXT")
    if "notes" not in columns:
        cursor.execute("ALTER TABLE alerts ADD COLUMN notes TEXT")

    # Migration: add response column to questions if missing
    cursor.execute("PRAGMA table_info(questions)")
    columns = [row[1] for row in cursor.fetchall()]
    if "response" not in columns:
        cursor.execute("ALTER TABLE questions ADD COLUMN response TEXT")

    # Auto-seed rooms from defaults if table is empty
    cursor.execute("SELECT COUNT(*) FROM rooms")
    if cursor.fetchone()[0] == 0:
        defaults = [
            ("101", "Margaret", "standard"),
            ("102", "Harold", "memory_support"),
            ("103", "Dorothy", "standard"),
        ]
        cursor.executemany(
            "INSERT INTO rooms (room_id, resident_name, mode) VALUES (?, ?, ?)",
            defaults,
        )

    conn.commit()
    conn.close()


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_rooms() -> dict:
    """Load all room profiles from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT room_id, resident_name, mode FROM rooms ORDER BY room_id")
    rooms = {}
    for row in cursor.fetchall():
        rooms[row["room_id"]] = {
            "resident_name": row["resident_name"],
            "mode": row["mode"],
        }
    conn.close()
    return rooms


# ==========================
# Auth helpers
# ==========================

def create_session(staff_name: str) -> str:
    """Create a new session token for a staff member."""
    token = secrets.token_urlsafe(32)
    now = datetime.utcnow()
    expires = now + dt.timedelta(hours=SESSION_EXPIRY_HOURS)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sessions (token, staff_name, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, staff_name, now.isoformat(), expires.isoformat()),
    )
    conn.commit()
    conn.close()
    return token


def get_session(token: Optional[str]) -> Optional[str]:
    """Validate a session token and return the staff name, or None if invalid/expired."""
    if not token:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT staff_name, expires_at FROM sessions WHERE token = ?", (token,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    if datetime.fromisoformat(row["expires_at"]) < datetime.utcnow():
        # Expired — clean up
        conn = get_db_connection()
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
        return None
    return row["staff_name"]


def delete_session(token: str):
    """Delete a session token."""
    conn = get_db_connection()
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()


def verify_pin(pin: str) -> bool:
    """Check if the provided PIN matches the stored hash."""
    return hashlib.sha256(pin.encode()).hexdigest() == STAFF_PIN_HASH


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
    acknowledged_at: Optional[str] = None
    resolved_at: Optional[str] = None
    acknowledged_by: Optional[str] = None
    resolved_by: Optional[str] = None
    notes: Optional[str] = None


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
def acknowledge_alert(alert_id: int, staff_name: Optional[str] = None, notes: Optional[str] = None):
    """Mark an alert as acknowledged."""
    now_str = datetime.utcnow().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE alerts SET status = 'ack', acknowledged_at = ?,
           acknowledged_by = ?, notes = COALESCE(?, notes)
           WHERE id = ? AND status = 'new'""",
        (now_str, staff_name, notes, alert_id),
    )
    conn.commit()
    cursor.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
    row = cursor.fetchone()
    conn.close()
    return Alert(**dict(row))


@app.post("/api/alerts/{alert_id}/resolve", response_model=Alert)
def resolve_alert(alert_id: int, staff_name: Optional[str] = None, notes: Optional[str] = None):
    """Mark an alert as resolved."""
    now_str = datetime.utcnow().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    # Append new notes to existing if both present
    if notes:
        cursor.execute("SELECT notes FROM alerts WHERE id = ?", (alert_id,))
        existing = cursor.fetchone()
        if existing and existing["notes"]:
            notes = existing["notes"] + "\n" + notes
    cursor.execute(
        """UPDATE alerts SET status = 'resolved', resolved_at = ?,
           resolved_by = ?, notes = COALESCE(?, notes)
           WHERE id = ?""",
        (now_str, staff_name, notes, alert_id),
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
    rooms = get_rooms()
    summary = {}

    for room_id, profile in rooms.items():
        cursor.execute(
            """SELECT COUNT(*) FROM alerts
               WHERE room_id = ? AND type = 'help'
               AND datetime(created_at) >= datetime('now', '-30 minutes')""",
            (room_id,),
        )
        help_count = cursor.fetchone()[0]

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

        cursor.execute(
            """SELECT COUNT(*) FROM alerts
               WHERE room_id = ? AND status != 'resolved'""",
            (room_id,),
        )
        active_count = cursor.fetchone()[0]

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


@app.get("/api/rooms/{room_id}")
def get_room(room_id: str):
    """Get a single room profile."""
    rooms = get_rooms()
    profile = rooms.get(room_id)
    if not profile:
        return JSONResponse({"error": "Unknown room"}, status_code=404)
    return {"room_id": room_id, **profile}


# ==========================
# Chat endpoint (LLM-powered)
# ==========================

@app.post("/api/room/{room_id}/chat", response_model=ChatResponse)
async def room_chat(room_id: str, req: ChatRequest):
    """Send a message to the Room Companion and get a response.

    Runs LLM chat and classification in parallel.
    Creates alert if classification detects a help request.
    """
    rooms = get_rooms()
    profile = rooms.get(room_id)
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
# Staff auth views
# ==========================

@app.get("/staff/login", response_class=HTMLResponse)
async def staff_login_page(request: Request, error: Optional[str] = None):
    """Staff login page."""
    return templates.TemplateResponse(
        "staff_login.html", {"request": request, "error": error or ""}
    )


@app.post("/staff/login")
async def staff_login(
    request: Request,
    staff_name: str = Form(...),
    pin: str = Form(...),
):
    """Handle staff login — validate PIN and create session."""
    staff_name = staff_name.strip()
    if not staff_name or not verify_pin(pin):
        return templates.TemplateResponse(
            "staff_login.html",
            {"request": request, "error": "Invalid name or PIN."},
            status_code=401,
        )

    token = create_session(staff_name)
    response = RedirectResponse(url="/staff", status_code=303)
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        max_age=SESSION_EXPIRY_HOURS * 3600,
        samesite="lax",
    )
    return response


@app.get("/staff/logout")
async def staff_logout(session_token: Optional[str] = Cookie(None)):
    """Log out staff — delete session and redirect to login."""
    if session_token:
        delete_session(session_token)
    response = RedirectResponse(url="/staff/login", status_code=303)
    response.delete_cookie("session_token")
    return response


# ==========================
# HTML views
# ==========================

@app.get("/room/{room_id}", response_class=HTMLResponse)
async def room_view(request: Request, room_id: str):
    """Room UI — resident-facing chat interface."""
    rooms = get_rooms()
    profile = rooms.get(room_id)
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
async def staff_view(
    request: Request,
    room_id: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    session_token: Optional[str] = Cookie(None),
):
    """Staff portal — alert dashboard with room status cards. Requires auth."""
    staff_name = get_session(session_token)
    if not staff_name:
        return RedirectResponse(url="/staff/login", status_code=303)

    rooms = get_rooms()
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

    for rid in rooms.keys():
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
        profile = rooms.get(alert["room_id"], {})
        alert["mode"] = profile.get("mode", "standard")

    return templates.TemplateResponse(
        "staff.html", {
            "request": request,
            "alerts": alerts,
            "profiles": rooms,
            "room_help_counts": room_help_counts,
            "room_orientation_counts": room_orientation_counts,
            "room_active_alerts": room_active_alerts,
            "room_latest_severity": room_latest_severity,
            "filter_room": room_id or "",
            "filter_severity": severity or "",
            "filter_status": status or "",
            "staff_name": staff_name,
        }
    )


@app.post("/staff/alerts/{alert_id}/ack")
async def staff_ack_alert(
    alert_id: int,
    notes: str = Form(""),
    session_token: Optional[str] = Cookie(None),
):
    """Acknowledge an alert with optional notes."""
    staff_name = get_session(session_token)
    if not staff_name:
        return RedirectResponse(url="/staff/login", status_code=303)
    acknowledge_alert(alert_id, staff_name=staff_name, notes=notes.strip() or None)
    return RedirectResponse(url="/staff", status_code=303)


@app.post("/staff/alerts/{alert_id}/resolve")
async def staff_resolve_alert(
    alert_id: int,
    notes: str = Form(""),
    session_token: Optional[str] = Cookie(None),
):
    """Resolve an alert with optional notes."""
    staff_name = get_session(session_token)
    if not staff_name:
        return RedirectResponse(url="/staff/login", status_code=303)
    resolve_alert(alert_id, staff_name=staff_name, notes=notes.strip() or None)
    return RedirectResponse(url="/staff", status_code=303)


@app.post("/staff/rooms/{room_id}/edit")
async def staff_edit_room(
    room_id: str,
    resident_name: str = Form(...),
    mode: str = Form(...),
    session_token: Optional[str] = Cookie(None),
):
    """Edit a room's resident name or care mode."""
    staff_name = get_session(session_token)
    if not staff_name:
        return RedirectResponse(url="/staff/login", status_code=303)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE rooms SET resident_name = ?, mode = ? WHERE room_id = ?",
        (resident_name.strip(), mode, room_id),
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url="/staff", status_code=303)


@app.get("/")
async def root():
    return RedirectResponse(url="/room/101")
