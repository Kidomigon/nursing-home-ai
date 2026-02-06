# Multi-Room Support – Plan (Nursing Home AI)

Goal: Move from a single hard-coded room (101) to multiple rooms (101, 102, 103, ...) while keeping the prototype simple.

## Current State

- `/room` assumes `room_id = "101"`.
- `RESIDENT_PROFILES` has a single entry for room 101.
- Alerts table stores `room_id` as text, but we only ever use "101".
- `/staff` lists alerts without filtering or grouping beyond `room_id` display.

## Target Behavior

- URL-based room selection:
  - `/room/{room_id}` shows the resident UI for that room.
- Multiple resident profiles:
  - `RESIDENT_PROFILES` contains entries for several rooms (e.g., 101, 102, 103), each with:
    - `resident_name`
    - `mode` (standard / memory_support)
- Alerts:
  - Continue storing `room_id` per alert.
  - `/staff` shows alerts from all rooms, sorted by time.
  - Later: simple filters (e.g., filter by room).

## Data Model Changes

1. **RESIDENT_PROFILES**

From:
```python
RESIDENT_PROFILES = {
    "101": {"resident_name": "Demo Resident", "mode": "standard"}
}
```

To something like:
```python
RESIDENT_PROFILES = {
    "101": {"resident_name": "Resident 101", "mode": "standard"},
    "102": {"resident_name": "Resident 102", "mode": "memory_support"},
    "103": {"resident_name": "Resident 103", "mode": "standard"},
}
```

(Room IDs stay simple strings; no new DB tables needed yet.)

2. **Alerts Table**

Already has a `room_id` column. No schema change needed; we just start using multiple values.

## Route Changes

1. **Room View**

From:
- `GET /room` → always room 101.

To:
- `GET /room/{room_id}` → dynamic room.
  - If `room_id` not in `RESIDENT_PROFILES`, show a simple "Unknown room" message or 404.
  - Pass `room_id`, `resident_name`, and `mode` to the template.

2. **Room Actions**

- `POST /room/help`
- `POST /room/question`

Update both to include `room_id` in the form/action URL or hidden input and route signature:

```python
@app.post("/room/{room_id}/help")
async def room_call_help(room_id: str, resident_name: str = Form(...)):
    ...
```

(Reusing the same handler but with room_id from the path keeps things clear.)

3. **Staff View**

- Keep `GET /staff` as is for now, but it will naturally show mixed alerts once we start generating alerts from multiple rooms.
- Later enhancements:
  - Add a query parameter to filter by room: `/staff?room_id=101`.
  - Add simple UI controls (dropdown) to filter in the template.

## Prototype UX Adjustments

- **Room Links:**
  - For testing, add quick links somewhere (e.g., a debug page or a simple list) to jump between `/room/101`, `/room/102`, `/room/103`.
- **Staff View:**
  - Make sure `room_id` column is clear and maybe slightly emphasized when scanning alerts.

## Implementation Order

1. Update `RESIDENT_PROFILES` to include 2–3 sample rooms.
2. Change `/room` route to `/room/{room_id}` and adjust the template to use `room_id` from the path.
3. Update help/question POST routes to accept `room_id` in the path.
4. Adjust links:
   - Root `/` → redirect to `/room/101` by default.
   - Staff template: ensure links back to a default room (e.g., `/room/101`).

This keeps the code simple while demonstrating multi-room support in a realistic way for the nursing-home prototype.
