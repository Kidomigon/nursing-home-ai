"""FastAPI prototype for Room Companion — nursing home AI assistant.

Features:
- LLM-powered conversational chat per room
- Intent classification with severity levels
- Real-time alert management for staff
- DB-driven multi-room support with resident profiles
- Per-user staff authentication (bcrypt) with role-based access
- CSRF protection on all staff POST endpoints
- Rate limiting on login, chat, and TTS
- Alert notes and attribution
- Voice input/output (handled client-side)
"""

import asyncio
import os
import subprocess
from datetime import datetime
import datetime as dt
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Request, Form, Cookie, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import sqlite3

from llm import load_api_keys, chat, classify, get_greeting, ClassificationResult
import auth

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "alerts.db"

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Room Companion")
app.state.limiter = limiter

# Rate limit error handler
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": "Too many requests. Please try again later."},
    )

# Static files & templates
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

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

    # Phase 4a: staff accounts table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'nurse',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            last_login_at TEXT
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

    # Migration: add staff_id and csrf_token to sessions
    cursor.execute("PRAGMA table_info(sessions)")
    columns = [row[1] for row in cursor.fetchall()]
    if "staff_id" not in columns:
        cursor.execute("ALTER TABLE sessions ADD COLUMN staff_id INTEGER")
    if "csrf_token" not in columns:
        cursor.execute("ALTER TABLE sessions ADD COLUMN csrf_token TEXT")

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

    # Auto-seed admin account if staff table is empty
    cursor.execute("SELECT COUNT(*) FROM staff")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            """INSERT INTO staff (username, display_name, password_hash, role, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            ("admin", "Admin", auth.hash_password("admin1234"), "admin",
             datetime.utcnow().isoformat()),
        )

    # Clear stale sessions without staff_id (from old PIN-based auth)
    cursor.execute("DELETE FROM sessions WHERE staff_id IS NULL")

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
# Auth dependencies
# ==========================

async def get_current_staff(session_token: Optional[str] = Cookie(None)):
    """FastAPI dependency: validate session and return staff info dict or None."""
    if not session_token:
        return None
    conn = get_db_connection()
    session = auth.get_session(conn, session_token)
    conn.close()
    return session


async def require_staff(staff=Depends(get_current_staff)):
    """Dependency that redirects to login if not authenticated."""
    if not staff:
        raise HTTPException(status_code=303, headers={"Location": "/staff/login"})
    return staff


async def verify_csrf(request: Request, staff=Depends(get_current_staff)):
    """Verify CSRF token on POST requests. Returns staff dict."""
    if not staff:
        raise HTTPException(status_code=303, headers={"Location": "/staff/login"})
    form = await request.form()
    if form.get("csrf") != staff.get("csrf_token"):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
    return staff


# ==========================
# HTTPS cert generation
# ==========================

def ensure_certs():
    """Generate self-signed certs if they don't exist."""
    cert_dir = BASE_DIR / "certs"
    key_path = cert_dir / "server.key"
    crt_path = cert_dir / "server.crt"

    if key_path.exists() and crt_path.exists():
        return

    os.makedirs(cert_dir, exist_ok=True)
    # Use clean environment to avoid LD_LIBRARY_PATH conflicts
    clean_env = {k: v for k, v in os.environ.items() if k != "LD_LIBRARY_PATH"}
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048",
        "-keyout", str(key_path), "-out", str(crt_path),
        "-days", "365", "-nodes", "-subj", "/CN=localhost"
    ], check=True, env=clean_env)


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
@limiter.limit("20/minute")
async def room_chat(request: Request, room_id: str, req: ChatRequest):
    """Send a message to the Room Companion and get a response."""
    rooms = get_rooms()
    profile = rooms.get(room_id)
    if not profile:
        return JSONResponse({"error": "Unknown room"}, status_code=404)

    resident_name = profile["resident_name"]
    mode = profile["mode"]
    user_message = req.message.strip()

    if not user_message:
        return ChatResponse(response="I didn't catch that. Could you say that again?", alert_created=False)

    chat_task = chat(room_id, resident_name, mode, user_message)
    classify_task = classify(user_message)
    response_text, classification = await asyncio.gather(chat_task, classify_task)

    now_str = datetime.utcnow().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO questions (room_id, resident_name, question, response, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (room_id, resident_name, user_message, response_text, now_str),
    )

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
@limiter.limit("30/minute")
async def text_to_speech(request: Request, req: TTSRequest):
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
@limiter.limit("5/minute")
async def staff_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    """Handle staff login — validate credentials and create session."""
    username = username.strip()
    if not username:
        return templates.TemplateResponse(
            "staff_login.html",
            {"request": request, "error": "Please enter your username."},
            status_code=401,
        )

    conn = get_db_connection()
    staff_record = auth.get_staff_by_username(conn, username)

    if not staff_record or not staff_record["is_active"]:
        conn.close()
        return templates.TemplateResponse(
            "staff_login.html",
            {"request": request, "error": "Invalid username or password."},
            status_code=401,
        )

    if not auth.verify_password(password, staff_record["password_hash"]):
        conn.close()
        return templates.TemplateResponse(
            "staff_login.html",
            {"request": request, "error": "Invalid username or password."},
            status_code=401,
        )

    token, csrf_token = auth.create_session(
        conn, staff_record["id"], staff_record["display_name"], staff_record["role"]
    )

    # Update last login
    conn.execute(
        "UPDATE staff SET last_login_at = ? WHERE id = ?",
        (datetime.utcnow().isoformat(), staff_record["id"]),
    )
    conn.commit()
    conn.close()

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
        conn = get_db_connection()
        auth.delete_session(conn, session_token)
        conn.close()
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
    staff=Depends(get_current_staff),
):
    """Staff portal — alert dashboard with room status cards. Requires auth."""
    if not staff:
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
            "staff_name": staff["staff_name"],
            "staff_role": staff["role"],
            "csrf_token": staff["csrf_token"],
        }
    )


@app.post("/staff/alerts/{alert_id}/ack")
async def staff_ack_alert(
    alert_id: int,
    notes: str = Form(""),
    csrf: str = Form(""),
    staff=Depends(get_current_staff),
):
    """Acknowledge an alert with optional notes."""
    if not staff:
        return RedirectResponse(url="/staff/login", status_code=303)
    if csrf != staff.get("csrf_token"):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
    acknowledge_alert(alert_id, staff_name=staff["staff_name"], notes=notes.strip() or None)
    return RedirectResponse(url="/staff", status_code=303)


@app.post("/staff/alerts/{alert_id}/resolve")
async def staff_resolve_alert(
    alert_id: int,
    notes: str = Form(""),
    csrf: str = Form(""),
    staff=Depends(get_current_staff),
):
    """Resolve an alert with optional notes."""
    if not staff:
        return RedirectResponse(url="/staff/login", status_code=303)
    if csrf != staff.get("csrf_token"):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
    resolve_alert(alert_id, staff_name=staff["staff_name"], notes=notes.strip() or None)
    return RedirectResponse(url="/staff", status_code=303)


@app.post("/staff/rooms/{room_id}/edit")
async def staff_edit_room(
    room_id: str,
    resident_name: str = Form(...),
    mode: str = Form(...),
    csrf: str = Form(""),
    staff=Depends(get_current_staff),
):
    """Edit a room's resident name or care mode."""
    if not staff:
        return RedirectResponse(url="/staff/login", status_code=303)
    if csrf != staff.get("csrf_token"):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE rooms SET resident_name = ?, mode = ? WHERE room_id = ?",
        (resident_name.strip(), mode, room_id),
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url="/staff", status_code=303)


# ==========================
# Staff management (admin only)
# ==========================

@app.get("/staff/manage", response_class=HTMLResponse)
async def staff_manage_page(request: Request, staff=Depends(get_current_staff)):
    """Staff account management — admin only."""
    if not staff:
        return RedirectResponse(url="/staff/login", status_code=303)
    if staff["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    conn = get_db_connection()
    staff_list = auth.list_staff(conn)
    conn.close()

    return templates.TemplateResponse(
        "staff_manage.html", {
            "request": request,
            "staff_list": staff_list,
            "staff_name": staff["staff_name"],
            "staff_role": staff["role"],
            "csrf_token": staff["csrf_token"],
        }
    )


@app.post("/staff/manage/create")
async def staff_manage_create(
    request: Request,
    username: str = Form(...),
    display_name: str = Form(...),
    password: str = Form(...),
    role: str = Form("nurse"),
    csrf: str = Form(""),
    staff=Depends(get_current_staff),
):
    """Create a new staff account — admin only."""
    if not staff:
        return RedirectResponse(url="/staff/login", status_code=303)
    if staff["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    if csrf != staff.get("csrf_token"):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

    if role not in ("nurse", "admin", "supervisor"):
        raise HTTPException(status_code=400, detail="Invalid role")

    conn = get_db_connection()
    existing = auth.get_staff_by_username(conn, username)
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="Username already exists")

    auth.create_staff(conn, username, display_name, password, role)
    conn.close()
    return RedirectResponse(url="/staff/manage", status_code=303)


@app.post("/staff/manage/{staff_id}/edit")
async def staff_manage_edit(
    staff_id: int,
    display_name: str = Form(...),
    role: str = Form(...),
    password: str = Form(""),
    csrf: str = Form(""),
    staff=Depends(get_current_staff),
):
    """Edit a staff account — admin only."""
    if not staff:
        return RedirectResponse(url="/staff/login", status_code=303)
    if staff["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    if csrf != staff.get("csrf_token"):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

    if role not in ("nurse", "admin", "supervisor"):
        raise HTTPException(status_code=400, detail="Invalid role")

    conn = get_db_connection()
    fields = {"display_name": display_name.strip(), "role": role}
    if password.strip():
        fields["password"] = password.strip()
    auth.update_staff(conn, staff_id, **fields)
    conn.close()
    return RedirectResponse(url="/staff/manage", status_code=303)


@app.post("/staff/manage/{staff_id}/deactivate")
async def staff_manage_deactivate(
    staff_id: int,
    csrf: str = Form(""),
    staff=Depends(get_current_staff),
):
    """Deactivate a staff account — admin only."""
    if not staff:
        return RedirectResponse(url="/staff/login", status_code=303)
    if staff["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    if csrf != staff.get("csrf_token"):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

    # Prevent self-deactivation
    if staff_id == staff["staff_id"]:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    conn = get_db_connection()
    auth.deactivate_staff(conn, staff_id)
    conn.close()
    return RedirectResponse(url="/staff/manage", status_code=303)


@app.get("/")
async def root():
    return RedirectResponse(url="/room/101")
