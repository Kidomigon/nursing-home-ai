# Pilot Plan – Nursing Home AI Assistant (Draft)

## 1. Pilot Overview

**Objective:**
Run a small, tightly-scoped pilot in a single facility wing to validate that:
- Residents can and will use per-room AI assistants for help and simple questions.
- The system can detect a small set of high-value safety events (help calls, distress) via audio.
- Staff find alerts useful and understandable, not just extra noise.
- Privacy concerns are addressed through local-first design and clear communication.

**Location:**
- One assisted-living or mixed-care facility where you have a relationship or can get access.
- Focus on a single hallway/wing for easier support.

**Duration:**
- 6–12 weeks (to capture enough real events and behavior patterns).

---

## 2. Scope & Participants

**Rooms:**
- 5–10 resident rooms in a single wing.
- Mix of:
  - ~6–8 residents in Standard mode.
  - ~2–3 residents who benefit from Memory Support mode (mild/moderate cognitive issues).

**Residents:**
- Able to speak and hear well enough to use a phone or smart speaker.
- Willing to participate and have basic privacy explained.
- For Memory Support residents, involve legal guardian/decision-maker where needed.

**Staff:**
- Nurses and CNAs on that wing.
- At least one nurse manager or charge nurse as a point person.

---

## 3. Hardware Setup (Pilot-Friendly)

**Per Room:**
- 1 × Android tablet (bedside) with:
  - Always-on power.
  - Mount or stand on the nightstand.
- 1 × simple handset or speaker/mic device:
  - Either a wired handset or Bluetooth handset paired to the tablet.
  - Large, easy-to-press “Talk” button for residents who prefer not to say a wake word.

**Network:**
- Facility Wi-Fi, with:
  - Stable coverage on the pilot wing.
  - Separate SSID/VLAN if needed for security.

**Fallback:**
- If Wi-Fi is unreliable, consider local-only logging + delayed sync, with clear limitations set for the pilot.

---

## 4. Software Scope (Pilot Features)

### 4.1 Resident Experience

**Modes:**
- Standard mode:
  - Conversational helper:
    - Simple questions (time, meals, appointments).
    - A few reminders (meals, key appointments).
  - Personality presets (e.g., Gentle & Quiet, Warm & Chatty).

- Memory Support mode:
  - Extra orientation cues ("You’re in your room at Oakview.").
  - Gentle repeated prompts (meals, time of day) within agreed limits.

**Input methods:**
- Pick up handset and talk.
- Press a large “Talk” button and speak.
- Wake word (optional, depending on tech).

### 4.2 Safety & Alerts

**In-scope detection (audio-only):**
- Clear help calls:
  - "Help", "I fell", "Nurse", "I need help", etc.
- Sustained distress:
  - Repeated cries for help.
  - Crying/shouting over a threshold duration.
- Simple fall suspicion:
  - Loud impact + immediate distress word/voice pattern.

**Out-of-scope for this pilot:**
- Full medical condition detection (e.g., detailed breathing analysis).
- Camera-based fall detection.
- Complex cognition/mood scoring.

### 4.3 Staff Portal

**Core views:**
- Alert feed:
  - Shows alerts sorted by severity and time.
  - Each alert: resident, room, time, type (emergency vs assistance), short explanation.
- Resident page:
  - Mode (Standard / Memory Support).
  - Personality preset.
  - Alert history with status (New / Acknowledged / Resolved).

**Staff actions:**
- Mark alert as acknowledged.
- Mark alert as resolved and optionally add a note.
- Adjust resident mode and preset (with appropriate approvals).

---

## 5. Privacy & Consent for the Pilot

**Resident-facing privacy story (plain language):**
- "This device is like a smart helper in your room. It listens for you to ask for help and to answer your questions."
- "Your conversations stay in your room by default. The staff will only see alerts, like if you ask for help or if it sounds like you might have fallen."
- "If it thinks you might be in danger, it will call the nurse even if you didn’t ask directly."

**Data handling:**
- Local-only:
  - Raw audio.
  - Full transcripts.
- Sent to backend:
  - Event summaries (type, time, severity, short explanation).
  - Configuration (mode, preset) and alert history.

**Consent flow:**
- Resident signs a simple pilot participation form.
- For memory care residents, involve guardian/decision-maker with clear explanation.
- Facility signs an agreement defining:
  - Scope of monitoring.
  - Data storage and access.
  - That this is a support tool, not a medical device.

---

## 6. Training & Support During Pilot

**Before launch:**
- 30–60 minute staff orientation:
  - What the system does and doesn’t do.
  - How to use the portal.
  - How to respond to alerts.
  - How to explain it to residents.

**Resident onboarding:**
- Brief per-resident setup:
  - Explain in plain language.
  - Set mode (Standard / Memory Support).
  - Choose personality preset.

**During pilot:**
- You (as the operator) available by phone/text for:
  - Technical issues.
  - Feedback collection.
- Weekly check-in with staff:
  - What’s working.
  - What’s annoying.
  - Any serious incidents or near-misses.

---

## 7. Metrics & Success Criteria

**Usage metrics:**
- Number of resident interactions per day/week (per room).
- Number of help calls handled through the system.

**Alert quality:**
- Count of emergency alerts vs actual emergencies (true vs obvious false alarms).
- Staff-rated usefulness of alerts (e.g., simple 1–5 rating collected weekly).

**Qualitative feedback:**
- Residents: do they find it helpful, annoying, comforting, confusing?
- Staff: does it help them respond faster or prioritize better?
- Admin: any privacy/complaint issues raised by families.

**Pilot success looks like:**
- At least a few real events where the system alerted staff appropriately.
- Staff report that most alerts are useful and not overwhelming.
- No major privacy backlash; residents generally comfortable with the device.

---

## 8. Exit & Next Steps

At the end of the pilot:
- Debrief with facility leadership and staff:
  - Keep, change, or stop?
  - What features are must-have vs nice-to-have for a wider rollout?
- Decide next direction:
  - Improve audio models and alert logic.
  - Expand to more rooms.
  - Move closer to custom hardware design if the concept proves out.

This pilot plan is intentionally conservative: it focuses on safety, clarity, and trust over fancy features, so you can learn fast without taking on too much risk.
