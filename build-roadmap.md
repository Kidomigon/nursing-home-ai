# Build Roadmap – Nursing Home AI Prototype

Goal: Build a working **end-to-end prototype** you can demo, then grow toward a pilot.
Stack (for now):
- Backend & API: **Python + FastAPI** (or Flask if needed, but FastAPI is better for async + docs).
- Storage: **SQLite**.
- Frontend: simple **HTML/JS web pages** served by the backend, so they run on desktop or tablet.

---

## Phase 1 – Single-Room Prototype (Happy Path)

**Objective:**
Show the full loop for a *single room* on your network:
Resident talks → device detects a help phrase → backend creates an alert → staff web page shows it and can mark it resolved.

### 1.1 Backend (FastAPI)

Endpoints:
- `POST /api/alerts` – receive alerts from the room device.
  - Body: { room_id, resident_name, type ("help"), message, timestamp }.
- `GET /api/alerts` – list active/recent alerts.
  - Query params: optional `status` (new/ack/resolved).
- `POST /api/alerts/{alert_id}/ack` – mark as acknowledged.
- `POST /api/alerts/{alert_id}/resolve` – mark as resolved.

Storage:
- SQLite DB with a single `alerts` table.

### 1.2 Resident Device (Web UI)

A simple web page (`/room`) that acts as the "tablet" for **Room 101**:

- Shows:
  - Resident name.
  - Big buttons:
    - "Call for Help".
    - "Ask a Question".
- V1 input:
  - Start with **text input** instead of real voice so we can wire the loop quickly.
  - Later swap in microphone + speech-to-text.

Behavior:
- If resident clicks "Call for Help":
  - POST to `/api/alerts` with type `"help"` and a generic message.
- If resident types a question:
  - For now, respond with a canned or simple AI answer (can stub this initially).

### 1.3 Staff Portal (Web UI)

A web page (`/staff`) that shows alerts:

- List of alerts with:
  - Room, resident, type, time, status.
- Buttons:
  - "Acknowledge".
  - "Resolve".

Implementation:
- Simple JS polling `/api/alerts` every few seconds.
- Call the ack/resolve endpoints.

**Deliverable of Phase 1:**
- Run a single Python app.
- Open `/room` in one browser ("resident").
- Open `/staff` in another ("nurse").
- Click "Call for Help" → see alert appear and handle it.

---

## Phase 2 – Basic Voice + Modes

**Objective:**
Make the resident UI feel more like a real assistant.

### 2.1 Voice Input (Prototype)

- Use Web Speech API (where available) or a simple cloud STT via backend.
- On "Talk" button:
  - Start recording.
  - Convert speech → text.
  - Show transcribed text and send it to backend for processing.

### 2.2 Help Phrase Detection

Server-side logic:
- Very simple detection first:
  - If text contains keywords ("help", "fell", "hurt", "nurse"), create a `help` alert.
- Log the text in a per-room local file or DB table (for future context), but **don’t expose raw transcripts in staff UI**.

### 2.3 Resident Modes (Standard vs Memory Support)

- Add a `resident_profiles` table or JSON config:
  - `mode`: "standard" or "memory_support".
- On `/room` page:
  - Change prompts / responses based on mode.
    - Standard: fewer prompts, direct answers.
    - Memory support: more orientation and reassurance.

---

## Phase 3 – Multi-Room + Cleaner Dashboard

**Objective:**
Support multiple rooms and a more realistic staff view.

Changes:
- Add `rooms` table with `room_id`, `resident_name`, `mode`.
- Modify alerts to link to `room_id` foreign key.
- `/room/{room_id}` route for per-room UI.
- `/staff` shows alerts grouped by room, with filters.

Optional extras:
- Simple login for staff (even just a shared password) so it’s not totally open.
- Basic trends like count of alerts per room for the last 24h.

---

## Phase 4 – Hardening Toward Pilot

When Phases 1–3 feel solid and you’re happy with the UX:

- Improve alert logic (fewer false positives).
- Add a configuration UI for modes and personality presets.
- Introduce more explicit privacy indicators in the resident UI.
- Start aligning the implementation with the pilot-plan requirements (5–10 rooms, metrics, etc.).

---

This roadmap is deliberately narrow: it gets you from **nothing** to a **working demo** quickly, then adds complexity in layers.
