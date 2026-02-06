# Vision Walkthrough – A Day with the System

This is a story-level walkthrough of how the system behaves once it’s deployed in a real facility. It assumes:
- Each resident has a bedside device with a small screen and a phone-style handset.
- The device can listen like a smart speaker (Alexa-style) when not on the handset.
- There is a staff web portal for alerts and basic configuration.
- Residents can be in **Standard** mode or **Memory Support** mode.

---

## Morning – Gentle Start to the Day

**Resident:** Mrs. Jones, 82, lives in assisted living. Her device is in **Standard** mode, personality preset **Gentle & Quiet**.

**07:30 AM – Wake-up Reminder**
- The device lightly chimes and shows a soft "Good morning" screen.
- In a calm voice: "Good morning, Mrs. Jones. Breakfast starts at 8:00. Would you like me to remind you again in 15 minutes?"
- Mrs. Jones, still in bed, just says toward the device: "Yes, remind me."
- The device recognizes her voice (smart-speaker-style wake) and confirms: "Okay, I’ll remind you in 15 minutes."

No alerts are sent anywhere; this is private, resident-only interaction.

---

## Late Morning – Questions and Companionship

**10:15 AM – Simple Questions**
- Mrs. Jones picks up the handset like a phone.
- "What time is my doctor’s appointment today?"
- Device: "You have an appointment at 2:00 PM today in the clinic downstairs. I’ll remind you at 1:15, if that’s okay."
- She says: "That’s fine, thank you."

Again, no staff involvement. The system logs locally that she likes short, direct answers and doesn’t need extra chatter.

---

## Early Afternoon – Memory Support Resident

**Resident:** Mr. Lee, 86, in the memory care wing. His device is in **Memory Support** mode, preset **Gentle & Reassuring**.

**1:00 PM – Orientation Check-in**
- The device has learned that Mr. Lee often seems confused in early afternoon.
- It gently prompts (audio + large text on screen): "Hi Mr. Lee, it’s just after 1:00 PM. You’re in your room at Oakview. Lunch is being served in the dining room. Would you like to go now?"
- He responds: "Where am I again?"
- Device: "You’re at Oakview, in your room. It’s a good time to have lunch. Do you want me to call a staff member to help you there?"
- He says: "Yes, please."

**Staff Portal View**
- Staff see a non-emergency task: "Room 312 – Assistance requested to go to lunch (Mr. Lee)." with a timestamp.
- A CNA marks it as acknowledged and goes to help him.

The system’s memory-support logic gives Mr. Lee extra orientation and prompts, but still respects his voice and choices.

---

## Mid-Afternoon – Passive Safety Listening

**3:40 PM – Background Listening (Smart Speaker Style)**
- Devices in both rooms are in passive listen mode, like a smart speaker:
  - Waiting for wake words or signs of distress.
  - Not streaming audio out; processing locally to detect keywords + tone + loud impacts.

In Mrs. Jones’s room, nothing special happens; she’s reading quietly.

In Mr. Lee’s room, he naps; the device quietly monitors but doesn’t disturb him.

---

## Evening – Real Emergency Event

**Resident:** Mrs. Jones again.

**7:10 PM – Possible Fall Detected**
- Mrs. Jones is walking from the bathroom back to bed.
- The device picks up:
  - A sharp thud sound.
  - Followed by a strained "Ow… help" from somewhere near the floor.
- The local AI classifies this as a likely emergency:
  - Sudden impact + distress word + tone indicating pain.

**Device Behavior (Room)**
- Device speaks clearly and loudly: "Mrs. Jones, I heard a loud noise and you asked for help. I’m calling the nurse now. If you can hear me, please try to speak to me."
- The screen lights up red with "Calling the nurse…".
- Mrs. Jones is groaning but not forming clear sentences.

**Staff Portal Behavior**
- An emergency alert appears at the top of the nurse dashboard:
  - "EMERGENCY – Room 204 – Possible fall and distress."
  - Short explanation: "Detected loud impact and ‘help’ from resident. No coherent response afterward."
  - Time: 7:10 PM.
- The system also triggers whatever emergency channel the facility has configured (pager/text/etc.).

**Nurse Response**
- A nurse taps "I’m responding" on the alert in the portal.
- Goes to Room 204.
- After helping Mrs. Jones, the nurse marks the alert as "Resolved" and optionally adds a note: "Found on floor near bed, minor bruising, no head impact, vital signs stable."

This resolution data helps tune the system over time (e.g., confirm that this type of audio pattern **should** be treated as high priority).

---

## Night – Quiet Monitoring & Respecting Privacy

**10:30 PM – Night Mode**
- Both residents’ devices go into Night Mode:
  - Screen dims, shows minimal info (time, a small icon indicating it’s listening for emergencies).
  - Proactive check-ins are disabled or very limited to avoid waking residents.
- The device still passively monitors for clear distress patterns:
  - Repeated cries for help.
  - Loud crashes.
  - Prolonged coughing / gasping.

If nothing happens, no data is sent to the backend beyond basic anonymous stats (for tuning, depending on privacy settings).

---

## How Staff See the Day

On the staff portal, looking back at the day:

- **Alerts feed** shows:
  - One emergency: Mrs. Jones’s fall event.
  - One non-emergency assistance request: Mr. Lee needing help to lunch.
- **Per-resident view**:
  - Mrs. Jones: shows a timeline with the fall incident and existing notes.
  - Mr. Lee: shows several gentle orientation prompts (local only) and a couple of non-emergency assistance tasks.

There are no raw transcripts; only summaries and metadata.

---

## How Residents Experience It

- Mrs. Jones experiences the device as a helpful, mostly quiet companion:
  - Answers questions.
  - Reminds her about appointments.
  - Only speaks up on its own a few times a day (based on her preferences).
  - In an emergency, it “has her back” and calls the nurse.

- Mr. Lee experiences it as a gentle, repetitive guide:
  - Reminds him where he is and what time it is.
  - Prompts for meals and activities.
  - Offers to get staff when he sounds confused or asks for help.

Neither of them feels like they are on camera or under constant surveillance. The device feels more like a smart phone/phone-helper than a spy.

---

## End-State Summary

When this system is "done" in the way we’re targeting:
- **Hardware**: a familiar, phone-like bedside unit with a handset, small screen, and always-listening audio like a smart speaker.
- **Resident AI**: one per room, customizable by mode (Standard vs Memory Support) and a couple of simple personality presets.
- **Staff Portal**: a clean web app focused on alerts, tasks, and per-resident summaries; little to no personality, just clarity.
- **Privacy**: conversations stay in the room by default; staff see only structured alerts and trend summaries.

This walkthrough is the north star for design and implementation decisions.
