# Build Roadmap — Nursing Home AI (Room Companion)

Goal: Build a working **end-to-end prototype** you can demo, then grow toward a pilot deployment in a real facility.

**Stack:**
- Backend: **Python + FastAPI**, async, auto-generated API docs
- Storage: **SQLite** (single file, zero config)
- Frontend: **HTML/JS** served by backend, runs on desktop or tablet
- LLM: **Groq** (llama-3.3-70b-versatile) primary, **OpenRouter** free fallback, canned response safety net
- TTS: **edge-tts** server-side (AriaNeural voice, mode-aware rate)
- STT: **Web Speech API** (browser-native, no server dependency)

---

## Phase 1 — Single-Room Prototype ✅ COMPLETE

**Objective:** Full alert loop for one room — resident talks, backend creates alert, staff sees and resolves it.

### What was built
- FastAPI backend with full alert CRUD (`POST/GET /api/alerts`, ack, resolve)
- SQLite `alerts` table with severity levels (emergency/urgent/routine/informational)
- Resident web UI (`/room/101`) with text chat input
- Staff portal (`/staff`) with JS polling, alert list, ack/resolve buttons
- LLM-powered responses via Groq API with intent classification
- Canned response safety net when LLM is unavailable

**Deliverable:** Run `uvicorn main:app`, open `/room/101` as resident, `/staff` as nurse. Full loop works.

---

## Phase 2 — Voice + Modes ✅ COMPLETE

**Objective:** Make the resident UI feel like a real voice assistant.

### What was built
- **Voice input** via Web Speech API (browser-native STT)
- **Voice output** via edge-tts server-side endpoint (`/api/tts`)
  - AriaNeural voice, mode-aware speech rate (slower for memory_support)
- **Help phrase detection** — LLM classifies intent with severity
  - Only emergency/urgent/routine create alerts; informational does not
- **Resident modes** — standard vs memory_support
  - memory_support: more reassurance, orientation cues, slower TTS

---

## Phase 3 — Multi-Room + Staff Auth ✅ COMPLETE

**Objective:** Scale to multiple rooms with proper data modeling and access control.

### What was built
- **`rooms` table** — DB-driven, auto-seeded with 3 residents:
  - Margaret (101, standard), Harold (102, memory_support), Dorothy (103, standard)
- **Per-room routing** — `/room/{room_id}` with resident profile loaded from DB
- **Staff authentication** — shared PIN "1234" (SHA-256), session cookies (8hr expiry)
- **Staff portal enhancements:**
  - Room editing (name, resident, mode, personality notes)
  - Alert notes + attribution (acknowledged_by, resolved_by, notes columns)
  - Room-based filtering
- **Alert notes modal** — staff can add context when acknowledging/resolving

---

## Phase 4 — Production Hardening 🔜 NEXT

**Objective:** Make it robust enough for a real pilot deployment.

### 4.1 Security & Auth
- [ ] Per-user staff accounts (replace shared PIN with individual logins)
- [ ] Password hashing with bcrypt + salt
- [ ] HTTPS via Let's Encrypt or self-signed cert
- [ ] Rate limiting on API endpoints
- [ ] CSRF protection on forms

### 4.2 Alert Intelligence
- [ ] Reduce false positives — confidence thresholds on LLM classification
- [ ] Alert deduplication (same resident, same issue within N minutes)
- [ ] Escalation rules — unacknowledged urgent alerts re-notify after timeout
- [ ] Alert history + trends per room (24h/7d charts)
- [ ] Shift handoff summary — auto-generated report of active/recent alerts

### 4.3 Reliability
- [ ] Health check endpoint (`/api/health`)
- [ ] Structured logging (JSON) with log rotation
- [ ] Graceful LLM degradation — track failure rate, auto-switch providers
- [ ] Database backups (scheduled SQLite `.backup` command)
- [ ] Process supervision (systemd unit file or Docker container)

### 4.4 UX Polish
- [ ] Configuration UI for room modes and personality presets
- [ ] Privacy indicators in resident UI ("This conversation is private")
- [ ] Resident photo/avatar support
- [ ] Larger touch targets for elderly users (accessibility audit)
- [ ] Night mode with dimmed display and quieter TTS

---

## Phase 5 — Smarter Conversations

**Objective:** Move beyond simple Q&A to contextual, memory-aware dialogue.

### 5.1 Conversation Memory
- [ ] Per-room conversation history stored in DB (rolling window)
- [ ] LLM receives recent context for continuity ("You mentioned your daughter earlier...")
- [ ] Configurable retention period (default 24h, memory_support mode longer)

### 5.2 Proactive Engagement
- [ ] Time-based check-ins ("Good morning Margaret, did you sleep well?")
- [ ] Medication reminders (configurable per resident)
- [ ] Activity suggestions based on time of day and resident preferences
- [ ] Gentle orientation cues for memory_support ("Today is Tuesday, February 15th")

### 5.3 Richer Intent Detection
- [ ] Multi-label classification (pain + location, emotional state + urgency)
- [ ] Sentiment tracking over time (detect mood decline patterns)
- [ ] Custom keyword/phrase lists per facility
- [ ] "I've fallen" vs "I fell yesterday" — temporal awareness to avoid false alerts

---

## Phase 6 — Full Duplex Voice (PersonaPlex)

**Objective:** Replace the turn-based voice pipeline with natural, overlapping conversation using NVIDIA PersonaPlex-7B.

### Why
The current pipeline (Web Speech API → text → LLM → text → edge-tts) creates unnatural pauses. Residents must wait for the system to finish speaking before they can talk. For elderly users, especially those with memory support needs, this feels robotic. Full duplex enables:
- **Simultaneous listening and speaking** — no awkward silences
- **Natural interruptions** — resident can interject mid-response
- **Backchanneling** — "mm-hmm", "I see" while resident talks
- **Faster response** — 170ms latency vs current multi-second pipeline

### Architecture Change
```
CURRENT:  Mic → Web Speech API → text → Groq LLM → text → edge-tts → speaker
                    (browser)              (cloud)          (server)

TARGET:   Mic → WebSocket audio stream → PersonaPlex-7B → audio stream → speaker
                    (browser)               (GPU server)        (browser)
```

### Requirements
- **NVIDIA GPU with 24GB+ VRAM** (A10G, RTX 3090/4090, or cloud equivalent)
- PersonaPlex-7B model weights (~14GB)
- WebSocket-based audio streaming endpoint
- Voice conditioning prompt (warm, calm, elderly-friendly voice)
- Role prompt integration with existing resident profiles

### Implementation Plan
- [ ] Acquire GPU access (local hardware, RunPod, or cloud instance)
- [ ] Set up PersonaPlex inference server (PyTorch + CUDA)
- [ ] Build WebSocket audio streaming endpoint (`/ws/voice/{room_id}`)
- [ ] Create voice conditioning prompts per resident mode
  - Standard: natural pace, friendly tone
  - Memory support: slower, warmer, more reassuring
- [ ] Integrate with existing alert system (PersonaPlex text output → intent classifier)
- [ ] Browser audio capture via MediaStream API (replace Web Speech API)
- [ ] Fallback to current pipeline when GPU unavailable
- [ ] Latency monitoring and quality metrics

### Status
**BLOCKED** — No NVIDIA GPU available on current hardware (AMD Vega iGPU, 17GB RAM). No free hosted API endpoint exists. Revisit when:
- Cloud GPU becomes available (RunPod ~$0.40/hr for RTX 4090)
- Community releases a quantized/CPU-compatible version
- A free inference endpoint appears on HuggingFace Spaces

### References
- [NVIDIA PersonaPlex Research](https://research.nvidia.com/labs/adlr/personaplex/)
- [Model on HuggingFace](https://huggingface.co/nvidia/personaplex-7b-v1)
- [GitHub Repository](https://github.com/NVIDIA/personaplex)
- [PersonaPlex Paper (PDF)](https://research.nvidia.com/labs/adlr/files/personaplex/personaplex_preprint.pdf)

---

## Phase 7 — Pilot Deployment

**Objective:** Deploy to a real nursing home wing (5-10 rooms) and validate with staff and residents.

### 7.1 Infrastructure
- [ ] Dedicated server or cloud instance (FastAPI + PersonaPlex if GPU available)
- [ ] Tablets provisioned per room (locked to Room Companion app)
- [ ] Network setup (isolated VLAN for privacy, local-only traffic option)
- [ ] Automated deployment (Docker Compose or Ansible)

### 7.2 Compliance & Privacy
- [ ] Data retention policy (configurable per facility)
- [ ] Consent workflow for residents/families
- [ ] Audit log for all staff actions
- [ ] No raw transcript exposure — only classified alerts reach staff
- [ ] Data export/deletion capability (resident discharge)

### 7.3 Metrics & Evaluation
- [ ] Alert response time tracking (created → acknowledged → resolved)
- [ ] False positive rate per room
- [ ] Resident engagement metrics (conversations/day, avg duration)
- [ ] Staff satisfaction survey integration
- [ ] Weekly automated report generation

### 7.4 Training & Onboarding
- [ ] Staff training guide (how to use portal, respond to alerts, edit rooms)
- [ ] Resident introduction protocol (gentle, opt-in, family involvement)
- [ ] IT setup guide (network, tablets, server)
- [ ] Troubleshooting runbook

---

## Status Summary

| Phase | Status | Key Milestone |
|-------|--------|---------------|
| 1. Single-Room Prototype | ✅ Complete | Full alert loop working |
| 2. Voice + Modes | ✅ Complete | Web Speech + edge-tts + LLM classification |
| 3. Multi-Room + Auth | ✅ Complete | 3 rooms, staff PIN, alert notes |
| 4. Production Hardening | 🔜 Next | Per-user auth, HTTPS, monitoring |
| 5. Smarter Conversations | 📋 Planned | Context memory, proactive engagement |
| 6. Full Duplex Voice | 🚫 Blocked | Needs NVIDIA GPU for PersonaPlex-7B |
| 7. Pilot Deployment | 📋 Planned | Real facility, 5-10 rooms |
