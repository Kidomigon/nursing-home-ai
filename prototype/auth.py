"""Authentication module for Room Companion staff portal.

Handles password hashing, staff account CRUD, session management with CSRF tokens.
"""

import secrets
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import bcrypt

DB_PATH = Path(__file__).parent / "alerts.db"
SESSION_EXPIRY_HOURS = 8


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ==========================
# Password hashing
# ==========================

def hash_password(password: str) -> str:
    """Hash a password with bcrypt (auto-salted)."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode(), stored_hash.encode())
    except Exception:
        return False


# ==========================
# Staff CRUD
# ==========================

def create_staff(conn: sqlite3.Connection, username: str, display_name: str,
                 password: str, role: str = "nurse") -> int:
    """Create a new staff account. Returns the new staff ID."""
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO staff (username, display_name, password_hash, role, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (username.strip().lower(), display_name.strip(), hash_password(password),
         role, datetime.utcnow().isoformat()),
    )
    conn.commit()
    return cursor.lastrowid


def get_staff_by_username(conn: sqlite3.Connection, username: str):
    """Look up a staff member by username. Returns dict or None."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM staff WHERE username = ?", (username.strip().lower(),))
    row = cursor.fetchone()
    return dict(row) if row else None


def get_staff_by_id(conn: sqlite3.Connection, staff_id: int):
    """Look up a staff member by ID. Returns dict or None."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM staff WHERE id = ?", (staff_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def list_staff(conn: sqlite3.Connection) -> list:
    """List all staff accounts."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM staff ORDER BY created_at")
    return [dict(row) for row in cursor.fetchall()]


def update_staff(conn: sqlite3.Connection, staff_id: int, **fields):
    """Update staff fields. Supported: display_name, role, is_active, password."""
    allowed = {"display_name", "role", "is_active"}
    updates = []
    params = []

    for key, value in fields.items():
        if key == "password" and value:
            updates.append("password_hash = ?")
            params.append(hash_password(value))
        elif key in allowed:
            updates.append(f"{key} = ?")
            params.append(value)

    if not updates:
        return

    params.append(staff_id)
    conn.execute(f"UPDATE staff SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()


def deactivate_staff(conn: sqlite3.Connection, staff_id: int):
    """Deactivate a staff account and clear their sessions."""
    conn.execute("UPDATE staff SET is_active = 0 WHERE id = ?", (staff_id,))
    conn.execute("DELETE FROM sessions WHERE staff_id = ?", (staff_id,))
    conn.commit()


# ==========================
# Session management
# ==========================

def create_session(conn: sqlite3.Connection, staff_id: int,
                   staff_name: str, role: str) -> tuple:
    """Create a new session. Returns (token, csrf_token)."""
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    now = datetime.utcnow()
    expires = now + timedelta(hours=SESSION_EXPIRY_HOURS)

    conn.execute(
        """INSERT INTO sessions (token, staff_name, created_at, expires_at, staff_id, csrf_token)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (token, staff_name, now.isoformat(), expires.isoformat(), staff_id, csrf_token),
    )
    conn.commit()
    return token, csrf_token


def get_session(conn: sqlite3.Connection, token: str):
    """Validate a session token. Returns dict with staff info or None."""
    if not token:
        return None

    cursor = conn.cursor()
    cursor.execute(
        "SELECT token, staff_name, expires_at, staff_id, csrf_token FROM sessions WHERE token = ?",
        (token,),
    )
    row = cursor.fetchone()
    if not row:
        return None

    if datetime.fromisoformat(row["expires_at"]) < datetime.utcnow():
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        return None

    # Look up role from staff table
    staff = get_staff_by_id(conn, row["staff_id"]) if row["staff_id"] else None
    role = staff["role"] if staff else "nurse"

    return {
        "token": row["token"],
        "staff_id": row["staff_id"],
        "staff_name": row["staff_name"],
        "role": role,
        "csrf_token": row["csrf_token"],
    }


def delete_session(conn: sqlite3.Connection, token: str):
    """Delete a session token."""
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()


def cleanup_expired_sessions(conn: sqlite3.Connection):
    """Remove all expired sessions."""
    now = datetime.utcnow().isoformat()
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
    conn.commit()
