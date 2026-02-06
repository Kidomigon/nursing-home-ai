# Personality & Privacy Model (Draft)

## Personality Profile (Per Room / Per Resident)

Each room assistant has a configurable personality profile:

- **Tone**: gentle ↔ direct
- **Talkativeness**: quiet ↔ chatty
- **Formality**: formal ↔ casual
- **Warmth**: clinical ↔ warm
- **Proactivity**: waits-to-be-asked ↔ regularly checks in

Profiles can be set via presets ("Very Gentle & Quiet", "Warm & Chatty") or fine-tuned sliders. They are configured collaboratively by staff and the resident, with optional input from family.

The assistant can propose adjustments over time based on how the resident actually interacts ("You tend to prefer short answers; should I be a bit quieter?").

## Privacy & Sharing Layers

Privacy is modeled in layers instead of a single on/off toggle. For each resident, the facility can configure (preferably with resident/family involvement):

1. **What can be shared with staff?**
   - Emergencies only (falls, acute distress, unresponsiveness).
   - Emergencies + serious health concerns (e.g., repeated confusion, suspected infection).
   - Emergencies + health concerns + long-term trends (sleep, mood, cognition patterns).
   - No raw conversation snippets unless explicitly requested in the moment.

2. **Who can change these settings?**
   - Resident (when capable).
   - Legal guardian / family member (when appropriate).
   - Designated staff roles for safety-critical overrides, with full audit logging.

3. **Emergency Override (Narrowly Scoped)**

In narrowly defined events, the assistant may escalate even if the resident normally keeps things very private:

- Suspected fall or loud impact plus distress.
- Clear acute distress (repeated crying/shouting for help).
- Apparent self-harm risk or severe confusion that could lead to harm.

Emergency overrides are:
- Transparent: visible in the audit log with rationale.
- Narrow: only apply to specific high-risk patterns.
- Documented: explained to residents/families during onboarding in plain language.

## Data Types

- **Local-only data** (lives on room device by default):
  - Full conversation history.
  - Fine-grained emotional state estimates.
  - Sensitive personal memories/stories.

- **Shared summaries & signals** (sent to backend):
  - Alert events (type, severity, time, short summary).
  - Trend indicators (e.g., "increase in night-time confusion over last 7 days").
  - Configuration state (current personality & privacy settings).

This separation ensures that residents experience the assistant as "their" companion, while staff see only what they need to act safely and effectively.
