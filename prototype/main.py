"""FastAPI prototype for nursing-home AI alerts

Phase 1: single-room prototype with:
- /api/alerts endpoints
- /room (resident UI, stubbed)
- /staff (staff portal, simple alert list)
"""
from datetime import datetime
import datetime as dt
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import sqlite3

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "alerts.db"

app = FastAPI(title="Nursing Home AI Prototype")

# In-memory store for last answer per room (prototype only)
LAST_ANSWERS = {}

# Static files & templates
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ==========================
# Database helpers (simple)
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
            created_at TEXT NOT NULL,
            acknowledged_at TEXT,
            resolved_at TEXT
        )
        """
    )

    # Questions table: log resident questions for future trend analysis
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id TEXT NOT NULL,
            resident_name TEXT NOT NULL,
            question TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# Run at startup
init_db()


# ==========================
# API models
# ==========================


class AlertCreate(BaseModel):
    room_id: str
    resident_name: str
    type: str
    message: str
    timestamp: Optional[str] = None


class Alert(BaseModel):
    id: int
    room_id: str
    resident_name: str
    type: str
    message: str
    status: str
    created_at: str
    acknowledged_at: Optional[str]
    resolved_at: Optional[str]


# ==========================
# API endpoints
# ==========================


@app.post("/api/alerts", response_model=Alert)
def create_alert(alert: AlertCreate):
    """Create a new alert (called by the room UI or device)."""
    now_str = alert.timestamp or datetime.utcnow().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO alerts
               (room_id, resident_name, type, message, status, created_at)
               VALUES (?, ?, ?, ?, 'new', ?)""",
        (alert.room_id, alert.resident_name, alert.type, alert.message, now_str),
    )
    conn.commit()
    alert_id = cursor.lastrowid

    cursor.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
    row = cursor.fetchone()
    conn.close()

    return Alert(**dict(row))


@app.get("/api/alerts", response_model=List[Alert])
def list_alerts(status: Optional[str] = None):
    """List alerts, optionally filtered by status."""
    conn = get_db_connection()
    cursor = conn.cursor()

    if status:
        cursor.execute("SELECT * FROM alerts WHERE status = ? ORDER BY created_at DESC", (status,))
    else:
        cursor.execute("SELECT * FROM alerts ORDER BY created_at DESC")

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
        """UPDATE alerts
               SET status = 'ack', acknowledged_at = ?
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
        """UPDATE alerts
               SET status = 'resolved', resolved_at = ?
               WHERE id = ?""",
        (now_str, alert_id),
    )
    conn.commit()

    cursor.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
    row = cursor.fetchone()
    conn.close()
    return Alert(**dict(row))


# ==========================
# Resident profile / modes
# ==========================

# Simple multi-room profile map for the prototype
RESIDENT_PROFILES = {
    "101": {
        "resident_name": "Resident 101",
        "mode": "standard",
    },
    "102": {
        "resident_name": "Resident 102",
        "mode": "memory_support",
    },
    "103": {
        "resident_name": "Resident 103",
        "mode": "standard",
    },
}

HELP_KEYWORDS = [
    "help",
    "fell",
    "fall",
    "nurse",
    "hurt",
    "pain",
    "emergency",
]


# ==========================
# HTML views (Phase 1 + simple modes)
# ==========================


@app.get("/room/{room_id}", response_class=HTMLResponse)
async def room_view(request: Request, room_id: str):
    """Room UI representing the resident device for a given room.

    Now supports multiple rooms via the path parameter.
    """
    profile = RESIDENT_PROFILES.get(room_id)
    if not profile:
        # Unknown room id
        return HTMLResponse(content=f"Unknown room: {room_id}", status_code=404)

    resident_name = profile["resident_name"]
    mode = profile["mode"]

    last_answer = LAST_ANSWERS.get(room_id)
    current_day = dt.datetime.now().strftime("%A")

    return templates.TemplateResponse(
        "room.html",
        {
            "request": request,
            "room_id": room_id,
            "resident_name": resident_name,
            "mode": mode,
            "last_answer": last_answer,
            "current_day": current_day,
        },
    )


@app.post("/room/{room_id}/help")
async def room_call_help(room_id: str, resident_name: str = Form(...)):
    """Handle 'Call for Help' button from room UI."""
    alert = AlertCreate(
        room_id=room_id,
        resident_name=resident_name,
        type="help",
        message="Resident requested help via button",
    )
    create_alert(alert)
    return RedirectResponse(url=f"/room/{room_id}", status_code=303)


@app.post("/room/{room_id}/question")
async def room_question(
    room_id: str,
    question: str = Form(""),
    resident_name: str = Form(...)
):
    """Handle 'Ask a Question'.

    Current behavior:
    - Log every question to the questions table.
    - If the text looks like a help/distress request, create a help alert.
    - Generate a simple canned response for common questions (time, meals, location)
      and store it in LAST_ANSWERS.
    """
    raw_question = (question or "").strip()
    text = raw_question.lower()
    now_str = datetime.utcnow().isoformat()

    # Log question
    if raw_question:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO questions (room_id, resident_name, question, created_at)
                   VALUES (?, ?, ?, ?)""",
            (room_id, resident_name, raw_question, now_str),
        )
        conn.commit()
        conn.close()

    # Simple keyword-based help detection
    if any(keyword in text for keyword in HELP_KEYWORDS):
        alert = AlertCreate(
            room_id=room_id,
            resident_name=resident_name,
            type="help",
            message=f"Possible distress from question input: '{raw_question}'",
        )
        create_alert(alert)

    # Simple canned responses
    answer = ""
    if text:
        if "where am i" in text or "what is this place" in text or "where is my room" in text:
            answer = f"You are in Room {room_id}."
        elif "time" in text:
            # Use local time string
            answer = f"It is now {datetime.now().strftime('%I:%M %p').lstrip('0')}"
        elif "breakfast" in text or "lunch" in text or "dinner" in text or "meal" in text:
            # Hard-coded schedule for prototype
            answer = "Breakfast is at 8:00 AM, lunch at 12:00 PM, and dinner at 5:30 PM."

    if answer:
        LAST_ANSWERS[room_id] = answer

    return RedirectResponse(url=f"/room/{room_id}", status_code=303)


@app.get("/staff", response_class=HTMLResponse)
async def staff_view(request: Request, room_id: Optional[str] = None):
    """Simple staff portal showing alerts, optionally filtered by room.

    Also computes a simple summary of help alerts in the last 30 minutes per room.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Main alert list (optionally filtered)
    if room_id:
        cursor.execute("SELECT * FROM alerts WHERE room_id = ? ORDER BY created_at DESC", (room_id,))
    else:
        cursor.execute("SELECT * FROM alerts ORDER BY created_at DESC")
    rows = cursor.fetchall()

    # Help alert counts in last 30 minutes per room (using SQLite time functions)
    cursor2 = conn.cursor()
    room_help_counts = {}
    room_orientation_counts = {}
    for rid in RESIDENT_PROFILES.keys():
        # Help counts
        cursor2.execute(
            """SELECT COUNT(*) FROM alerts
                   WHERE room_id = ? AND type = 'help'
                   AND datetime(created_at) >= datetime('now', '-30 minutes')""",
            (rid,),
        )
        count_row = cursor2.fetchone()
        room_help_counts[rid] = count_row[0] if count_row else 0

        # Orientation confusion counts (last 7 days)
        cursor2.execute(
            """SELECT COUNT(*) FROM questions
                   WHERE room_id = ?
                   AND datetime(created_at) >= datetime('now', '-7 days')
                   AND (lower(question) LIKE '%where am i%'
                        OR lower(question) LIKE '%what time%'
                        OR lower(question) LIKE '%what day%')""",
            (rid,),
        )
        orient_row = cursor2.fetchone()
        room_orientation_counts[rid] = orient_row[0] if orient_row else 0

    conn.close()

    alerts = [dict(row) for row in rows]

    # Enrich alerts with mode info from RESIDENT_PROFILES
    for alert in alerts:
        profile = RESIDENT_PROFILES.get(alert["room_id"], {})
        alert["mode"] = profile.get("mode", "standard")

    return templates.TemplateResponse(
        "staff.html", {
            "request": request,
            "alerts": alerts,
            "room_help_counts": room_help_counts,
            "room_orientation_counts": room_orientation_counts,
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


# Root redirect
@app.get("/")
async def root():
    # Default to room 101 for now
    return RedirectResponse(url="/room/101")
