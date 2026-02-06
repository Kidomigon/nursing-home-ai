# Nursing Home AI – UI & Market Research Plan

## Goals

1. Understand how staff currently see and act on alerts, confusion, and resident status.
2. Borrow proven UI patterns from existing tools instead of inventing everything.
3. Stress-test our current prototype flows (/room and /staff) against real-world expectations.

## Target Surfaces to Study

### 1. Staff-facing systems

Look at (screenshots, marketing pages, demo videos):

- Nurse call systems / alert dashboards
  - How they show: room, resident, alert type, time, status.
  - How they prioritize / highlight urgent vs routine.
  - Filters (by room, by severity, by status, by time window).
- Long-term care / assisted living EHR front pages
  - Resident summary strips / cards.
  - Any flags for fall risk, cognition, behavior changes.
- Rounding / task management apps for nurses
  - How tasks and alerts coexist.
  - How they display “what’s changed” since last round.

### 2. Resident-facing systems

- In-room terminals / bedside tablets used in LTC or hospitals.
  - Font sizes, contrast, iconography.
  - How they explain “call for help” vs “ask a question”.
  - How they show orientation info (date, time, place) for memory support.

## Questions We Want Answered

### Staff UI questions

- What’s the minimal info a nurse wants to see in a list row for an alert?
  - e.g., Time, Room, Resident, Type, Source, Status, short message.
- How are repeated alerts from the same room typically summarized?
- How do systems visually indicate:
  - "Unacknowledged" vs "acknowledged" vs "resolved"?
  - "Spike" in alerts from the same room?
- How are cognitive/behavioral flags shown (if at all)?
  - Is it badges, icons, colored labels, separate panel?

### Resident UI questions

- For memory support UIs:
  - How is orientation info phrased ("You are at...", "Today is...")?
  - How often is it repeated / shown?
- For call-for-help:
  - Is it a single big button? Multiple options? Do they confirm?
- For voice-based question flows:
  - Are there clear, simple hints for what you can ask?
  - How do they avoid confusing "help" requests with general questions?

## How We’ll Use the Findings

### For /staff

- Re-evaluate table layout:
  - Column order and naming (e.g., Time → "Time", Type → maybe an icon + label).
  - Whether to add a short “risk summary” row/strip per room at the top.
- Decide on visual language for:
  - High help-frequency rooms (we currently use `!`).
  - High orientation-question rooms.
- Decide if we should:
  - Show a mini per-room card above the table.
  - Move some explanations (legends) into a sidebar or hover.

### For /room

- Refine Memory Support intro card text using language similar to proven UIs.
- Adjust font sizes and layout (one or two big actions per screen, maximum).
- Possibly add a gentle always-on orientation strip (e.g., "You are in Room 102 – Tuesday afternoon").

## Execution Plan

1. Collect
   - Grab 10–20 screenshots / marketing pages / demo videos of:
     - Nurse call dashboards.
     - LTC / assisted living EHR front pages.
     - Resident / bedside tablet UIs for seniors.

2. Annotate
   - For each screenshot:
     - Note what’s on screen (elements, layout).
     - Note what we like / dislike.
     - Note any patterns (e.g., always show room + resident photo together).

3. Synthesize
   - Extract 5–10 concrete UI rules/patterns we want to borrow.
   - Decide on: table layout, color coding, icon usage, resident-card layout.

4. Apply to prototype
   - Update `/staff` HTML/CSS to match 2–3 chosen patterns.
   - Update `/room` memory-support view using best orientation language and layout patterns.

## What We Already Have (to Compare Against)

- `/room/{room_id}`
  - Call for Help button.
  - Ask a Question with voice and text.
  - Memory Support mode with basic orientation copy and day-of-week.

- `/staff`
  - Alerts table with status, type, source icon, and actions.
  - Per-room help alerts (last 30 min) with thresholds.
  - Per-room orientation-question counts (last 7 days) with thresholds.

We’ll use the research to critique these current screens and iterate toward something that looks and feels closer to what nurses and administrators already trust.