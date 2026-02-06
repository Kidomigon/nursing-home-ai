# MVP Scope (Draft)

## Goal of MVP
Prove that per-room AI assistants can:
- Provide **useful companionship and reminders** to residents.
- Detect a small set of **high-value safety events**.
- Deliver **clear, actionable alerts** to staff.

All while:
- Keeping conversations private by default.
- Fitting into real-world facility workflows.

Deployed in **one small facility or wing**, audio-only, on dedicated room devices.

---

## In-Scope Features (MVP)

### 1. Room Assistant – Core Capabilities
- Voice-based interaction (wake phrase or button) with:
  - Simple companionship (small talk, weather, basic questions).
  - Reminders tied to facility schedule (meals, activities) and individual needs.
- Configurable personality presets per resident:
  - At least 2–3 presets (e.g., "Gentle & Quiet", "Warm & Chatty").
- Basic proactive check-ins (optional):
  - E.g., "Would you like me to check on you each evening?" with easy opt-out.

### 2. Safety & Alerting – MVP Set
- Audio-only detection of a **limited set** of events:
  - Explicit help calls ("Help", "I fell", "I need a nurse").
  - Sustained distress (crying, repeated calling for help).
- Simple severity classification:
  - Emergency vs non-emergency.
- Emergency behavior:
  - Speak to resident when possible ("I'm calling the nurse now.").
  - Send structured alert to staff dashboard + notify via agreed channel (e.g., text/pager integration if available).

### 3. Staff Dashboard – MVP
- Login-protected web interface for one facility.
- Views:
  - **Alert feed** (sorted by severity and time).
  - **Per-resident page** with alert history and current settings.
- For each alert:
  - Resident, room, time.
  - Alert type (e.g., "Help call", "Distress").
  - Short explanation; no raw transcript.
  - Status (new, acknowledged, resolved).

### 4. Privacy & Consent – MVP
- Default behavior:
  - Conversations stay on the room device.
  - Only event summaries + alert metadata go to the backend.
- Simple setting per resident:
  - What can be shared with staff beyond emergencies (e.g., serious concerns vs emergencies only).
- Narrow emergency override policy documented and visible to staff.

### 5. Basic Admin / Configuration
- Map rooms ↔ residents.
- Set personality preset for each resident.
- Set simple privacy preference for each resident.
- Configure who receives emergency alerts (roles/contacts).

---

## Out of Scope for MVP (Explicitly Later)

- Cameras or video-based detection.
- Full EHR/EMR integration.
- Detailed cognitive/mood trend analytics.
- Family / care-circle portal.
- Advanced NLP understanding of complex medical questions.
- Multi-facility deployment and cross-facility analytics.

---

## MVP Success Signals

Qualitative:
- Residents describe the assistant as helpful and non-intrusive.
- Staff feel alerts are mostly useful (not just noise) and easy to understand.

Quantitative (even if rough):
- Number of emergency alerts that correspond to real events vs obvious false alarms.
- Response times to emergency alerts compared to baseline.
- Adoption: how many residents actually talk to their assistant at least a few times a week.

These signals help decide whether to invest in the more advanced roadmap items (trends, integrations, multi-facility support, etc.).
