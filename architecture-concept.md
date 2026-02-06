# Architecture Concept (Draft)

This is a **v1 architecture draft** for the nursing home AI platform. It is meant to be updated as we learn more from research and pilots.

Assumptions for early pilots:
- Room hardware is **off-the-shelf**: Android tablet (bedside) + simple handset (wired or Bluetooth) + always-on mic/speaker.
- Audio is processed **locally** on the room device where possible.
- Backend runs in a secure cloud or on-prem environment.
- Staff access a **web portal** from existing PCs or tablets.

---

## 1. High-Level Components

1. **Room Device (Per Room)**
   - Hardware: Tablet + handset + mic/speaker.
   - Software:
     - Resident Voice Interface (conversation, reminders).
     - Local Audio Sentinel (distress/help detection, basic fall suspicion).
     - Local Profile Store (resident mode, personality preset, local conversation history).
     - Sync Client (securely sends events and configuration updates to/from backend).

2. **Backend Services (Facility / Cloud Layer)**
   - **API Gateway** – single entry point for room devices and staff portal.
   - **Event Ingestion & Triage Service** – receives alerts/events from room devices, classifies/prioritizes.
   - **Resident State & Config Service** – stores non-sensitive resident config and alert/trend data.
   - **Alerting & Notification Service** – routes emergency alerts to staff portal and optional paging/SMS/email systems.
   - **Auth & Access Control Service** – manages staff accounts, roles, and permissions.

3. **Staff Portal (Web App)**
   - Frontend web UI (alerts feed, resident pages, basic settings).
   - Backend API calls into the services above.

4. **Admin & Integration Layer (Later)**
   - Hooks for EHR/EMR integration.
   - Multi-facility management.
   - Analytics/reporting.

---

## 2. Room Device Architecture

### 2.1 Modules

- **Voice UI Module**
  - Handles wake word / push-to-talk.
  - Converts speech ↔ text for resident interactions.
  - Talks to a language model (local or remote, depending on constraints) to generate responses.
  - Applies the resident's **mode** and **personality preset** to control tone and verbosity.

- **Local Audio Sentinel Module**
  - Continuously monitors audio input (smart-speaker style) for:
    - Help/distress words ("help", "I fell", "nurse", etc.).
    - Distress tone (shouting, crying).
    - Sudden loud impacts.
  - Runs simple models locally to classify potential events into:
    - No event.
    - Non-emergency assistance (e.g., "can someone help me to the bathroom?").
    - Emergency (possible fall, severe distress).
  - Packages only **structured events** and small summaries for the backend; **no raw audio** is sent.

- **Resident Profile & Mode Module**
  - Stores per-resident settings locally:
    - Mode: **Standard** or **Memory Support**.
    - Personality preset (e.g., Gentle & Quiet, Warm & Chatty).
    - Local preferences (e.g., mute at night, preferred check-in times).
  - Ensures that the Voice UI and Audio Sentinel respect these settings.

- **Sync & Security Module**
  - Handles encrypted communication with backend.
  - Sends:
    - Event payloads (alerts, assistance requests).
    - Minimal, privacy-preserving trend summaries.
  - Receives:
    - Configuration updates (mode/preset changes, thresholds).
    - Software updates (when supported).

---

## 3. Backend Architecture

### 3.1 Event Ingestion & Triage

- Receives events from each room device, such as:
  - `EMERGENCY_FALL_SUSPECTED`
  - `HELP_CALL`
  - `ASSISTANCE_REQUEST`
- Validates and normalizes events into a common format.
- Applies facility-level rules to:
  - Prioritize by severity.
  - De-duplicate noisy events (e.g., multiple non-emergency help calls within seconds).

### 3.2 Resident State & Config Store

- Stores **non-sensitive** resident data:
  - Link: Resident ↔ Room.
  - Mode (Standard/Memory Support) and personality preset.
  - Alert history (type, time, status, short description).
  - Simple trend indicators (e.g., count of emergencies vs non-emergencies over time).
- Does **not** store full conversation transcripts or raw audio.

### 3.3 Alerting & Notification Engine

- Converts triaged events into:
  - Emergency alerts → high-priority items in staff portal + optional push/pager/SMS.
  - Non-emergency tasks → lower-priority items or check-in suggestions.
- Tracks alert lifecycle:
  - New → Acknowledged → Resolved.

### 3.4 Auth & Access Control

- Manages facility staff accounts and roles (Nurse, CNA, Admin).
- Enforces data access limits (who can see which residents/alerts).
- Logs access (audit trail) for privacy/compliance.

---

## 4. Staff Portal Architecture

- **Frontend** (web UI):
  - Alert feed view.
  - Resident detail view.
  - Basic settings management (mode, preset, contacts for alerts).

- **Backend** (reuse main backend services):
  - Reads from Resident State & Config.
  - Updates settings via Config Service.
  - Updates alert status via Alerting Engine.

The portal itself is mostly a "window" into the backend; it does not store sensitive data on the client side beyond active session info.

---

## 5. Data Flow & Privacy Boundaries

### 5.1 Local-Only Data (Room Device)
- Full conversation transcripts.
- Fine-grained emotional estimates.
- Audio waveforms.

These stay on the device by default.

### 5.2 Shared Data (Backend)
- Structured events:
  - Event type, timestamp, severity, confidence, room/resident ID.
  - Short textual summary ("Detected loud impact and 'help' from resident, no response after prompt").
- Configuration:
  - Mode, preset, notification preferences.
- Trend counts (e.g., "3 emergency alerts this week").

No raw audio or full transcripts are stored in the backend.

---

## 6. Evolution Toward Custom Hardware

Over time, the room device could move from "tablet + handset" to:
- Custom bedside unit with integrated handset, mic/speaker, and screen.
- Possibly an embedded OS with more robust local inference for audio models.

The **logical architecture stays the same**:
- Room Device runs Voice UI + Audio Sentinel + Sync.
- Backend handles events, state, alerts, and portal.

Only the physical form factor and some implementation details change.

---

This document is intentionally high-level and will be refined as we choose specific technologies, deployment models (on-prem vs cloud), and integration points with real facilities.
