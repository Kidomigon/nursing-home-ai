# Personas & Journeys (Draft)

## Personas

### 1. Resident (Standard)
An older adult living in a nursing home or assisted living facility who can generally make their own decisions.

Key traits:
- Varies in independence but can usually express preferences.
- Mixed comfort with technology; many prefer simple, phone-like, voice-first interaction.
- Wants safety and reassurance **without** feeling watched or infantilized.

What matters to them:
- Feeling respected and listened to.
- Clear control over how much the assistant talks, what it shares, and when.
- Companionship that doesn’t feel fake or intrusive.

---

### 2. Resident (Memory Care Modifier)
A resident with moderate to significant cognitive impairment, often in a memory care unit.

This is not a different "type of person" but a **modifier** on the resident persona that changes how the system behaves:

Key traits:
- May not reliably remember settings or past conversations.
- May repeat questions or feel easily disoriented.
- Often has a legal guardian or designated decision-maker.

What matters to their experience:
- Extra simplicity and repetition without sounding condescending.
- Extra safety checks and gentle orientation ("You’re in your room at Sunny Acres. It’s Tuesday morning.").
- Privacy and consent handled with respect but with more involvement from clinical/legal frameworks.

---

### 3. Frontline Staff (Nurse / CNA / Caregiver)

Key traits:
- Overloaded, time-poor, often managing multiple residents at once.
- Uses a mix of paper notes, resident portals, nurse call systems, and their own memory.

What matters to them:
- Fewer "false alarm" interruptions.
- Clear, prioritized alerts that are obviously actionable.
- Tools that fit into their existing workflow instead of adding yet another system to check.

---

### 4. Facility Leadership / Admin

Key traits:
- Responsible for safety outcomes, regulatory risk, and budgets.
- Thinking about reputation, family satisfaction, and staff retention.

What matters to them:
- Tools that genuinely improve safety and satisfaction without creating huge legal/privacy headaches.
- Clear boundaries around what is monitored and how data is handled.
- Evidence (stories + metrics) that the system helps residents and staff.

---

## Key Journeys (Draft)

### Journey 1 – Resident Sets Up Their Room Assistant
1. Staff member introduces the assistant in simple, human language ("This is a helper that lives in your room. It can talk with you and call us if it thinks you might need help.").
2. Resident goes through a short conversation-based setup:
   - Preferred name and how the assistant should address them.
   - Basic personality choices (gentle vs direct, quiet vs chatty).
   - Comfort level with proactive check-ins ("Do you want me to ask how you're doing once a day, or only when you call me?").
3. Staff confirms safety defaults (emergency overrides) and explains them in plain language.
4. The assistant summarizes: "I'll keep your conversations private. If I think you may be in danger, I'll still call the staff so they can help."

---

### Journey 2 – Resident Calls for Help and System Escalates
1. Resident says "Help" or "I fell" or uses another natural phrase.
2. Room assistant analyzes tone + wording + context (time of day, impact sound, etc.).
3. If classified as an emergency:
   - It speaks to the resident: "I'm calling the nurse. Are you hurt?" (if they are responsive).
   - It sends an emergency alert to the staff dashboard + existing nurse call channels.
4. Staff sees a clear, short alert: who, where, what, and why (short explanation).
5. After staff response, the system logs the resolution and uses it to refine future alerts.

---

### Journey 3 – Trusted Contact Helps Configure Privacy Settings
1. Resident invites a trusted contact (e.g., adult child, guardian) to help set things up.
2. On a simple screen (or via staff-assisted process), they review:
   - What the assistant can share with staff.
   - What can be summarized for the care circle (if anything).
3. They pick a setting like: "Staff can see emergencies and serious health concerns. Care circle gets occasional high-level wellness summaries (no conversation details)."
4. The system records who set which preferences and when, with the resident's confirmation when possible.

---

### Journey 4 – Staff Reviews Trends and Adjusts Care
1. Over a few weeks, the system notices a pattern: more night-time confusion events for a resident.
2. The staff dashboard surfaces a trend alert: "Increase in night-time confusion over last 14 days" with a simple visual.
3. Staff reviews the alert, sees a short explanation (no raw transcripts), and adds a note or task:
   - "Flag for provider visit" or "Increase evening check-ins for now."
4. The assistant adjusts its own behavior accordingly (e.g., more evening reassurance check-ins if allowed by privacy settings).

---

These journeys will be refined as we learn more about real facility workflows and resident preferences, but they give us concrete user stories to design around.
