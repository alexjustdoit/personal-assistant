# Changelog

All notable changes to this project are documented here.

---

## [Proposed]

### GUI-based setup wizard
Replace the terminal setup wizard with a browser-based first-run flow. When `config.yaml` is missing, the app serves a setup page instead of the main UI. User fills in a multi-step form, submits, config is saved, and the app prompts a restart. Requires lazy config loading and a `POST /api/setup` endpoint.

### Smart home — Govee integration
Control Govee devices via the Govee Developer API. Planned device support (subject to API compatibility — verify at developer.govee.com):
- **H6008 smart bulbs** — on/off, brightness, color temperature (likely supported)
- **RGBIC Lyra floor lamp** — on/off, brightness, color/scene control (RGBIC support varies by model)
- **Govee Life Smart air purifier** — on/off, mode/fan speed (appliance API support uncertain)

Control via chat ("turn off the bedroom light", "set the lamp to red") using LLM intent detection and Govee API calls.

### UI quality of life
- New chat button — start a fresh conversation without clearing history
- Thinking indicator — show a subtle animation while waiting for the first token
- Markdown rendering in chat bubbles — code blocks, bold, lists rendered properly
- Mobile layout improvements — better spacing and touch targets on iPhone

### Expanded proactive layer
- Proactive memory suggestions — assistant surfaces follow-ups based on things you've mentioned ("you mentioned booking a dentist appointment last week — did you get around to it?")
- Weekly digest — summary of the week delivered via ntfy on a configured day
- Reminder snooze — ntfy action buttons to snooze a reminder by 30 minutes or 1 hour

### Runtime config editing
Allow the assistant to update certain config values (e.g. news topics) through conversation. Requires a config write endpoint and live reload of affected services without restart.

### Portfolio / showcase
- `DEMO.md` with screenshots and feature walkthrough
- Demo video or GIF showing voice input, morning briefing, and smart home control

---

## [0.5] — 2026-03-30

### Added — Proactive Layer
- Morning briefing delivered via ntfy — assembles weather, calendar events, news headlines, and reminders, narrated by the LLM
- Weather integration via OpenWeatherMap API (free tier) — imperial or metric
- News digest via Tavily API — user-defined topics, up to 2 headlines each
- Calendar integration via iCal URL — works with Google Calendar, Outlook, and Apple Calendar without OAuth
- Reminders — detected from natural language in chat via LLM extraction, stored in SQLite, due-time parsed via `dateparser`
- Push notifications via ntfy — reminder alerts (high priority) and morning briefing delivery
- APScheduler background scheduler — cron job for morning briefing, 1-minute interval for reminder checks
- Pending reminders injected into system prompt so the assistant knows about them conversationally

### Added — Onboarding Wizard
- `setup.py` — interactive CLI wizard covering all config sections
- Live Ollama connection test during setup with model availability check
- Timezone picker with numbered list of common options
- Warns before overwriting an existing `config.yaml`
- `run.py` now gives a clear message if `config.yaml` is missing instead of crashing

### Added — Windows Service
- `service/install.ps1` — installs app as `PersonalAssistant` Windows service via NSSM, auto-starts on boot, logs to `data/logs/` with 5MB rotation
- `service/uninstall.ps1` — cleanly removes the service
- `service/game_on.bat` — stops service before gaming (self-elevating to admin)
- `service/game_off.bat` — starts service after gaming (self-elevating to admin)

### Fixed
- Setup wizard API key fields now show input when pasting — replaced `getpass` with regular `input()` for all fields

### Added — `complete()` method on LLMRouter
- Non-streaming completion using local Ollama, used for reminder extraction and briefing narration

---

## [0.4] — 2026-03-30

### Added — Persistent Memory
- SQLite database (`data/conversations.db`) stores full conversation history per session
- ChromaDB vector store (`data/chroma/`) for semantic personal memory
- Session IDs generated in browser `localStorage`, passed as WebSocket query parameter
- Relevant memories retrieved on each message and injected into the system prompt automatically
- Explicit memory detection from chat: *"remember that..."*, *"note that..."*, *"don't forget..."*, *"keep in mind..."*
- Conversation history reloaded on page refresh — welcome screen skips if prior conversation exists
- `GET /api/history/{session_id}` endpoint for frontend history load
- Reminders table added to SQLite (used by Phase 4)
- `data/` directory gitignored — conversations, memory, and logs never pushed to repo

---

## [0.3] — 2026-03-30

### Added — Voice
- Speech-to-text via `faster-whisper` — runs locally on GPU, `base` model by default
- Text-to-speech via Kokoro TTS — local, free, near-API quality
- `POST /api/voice/transcribe` — accepts browser audio blob, returns transcribed text
- `POST /api/voice/speak` — accepts text, returns WAV audio
- `GET /api/voice/status` — reports STT/TTS availability to frontend
- Mic button in UI — click to record, click to stop, pulses red while recording, shows spinner while transcribing
- Speaker toggle in header — defaults on when TTS is available, hides if TTS disabled in config
- Voice responses default to on when TTS is configured; TTS failure is non-fatal (text always shown)
- STT and TTS both lazy-load their models on first use to avoid slow startup

---

## [0.2] — 2026-03-30

### Added — Provider Selector
- Dropdown in header lets you switch between Ollama, Claude, and OpenAI at runtime without touching config
- `GET /api/providers` endpoint returns available providers based on configured API keys
- Only providers with a configured API key are shown — fresh installs show Ollama only
- Selected provider sent with each WebSocket message

### Added — Welcome Screen
- Shown on first load when no messages exist
- Brief description of the assistant and four clickable suggestion chips
- Clicking a chip fills and sends the prompt immediately
- Disappears automatically once the first message is sent

---

## [0.1] — 2026-03-30

### Added — Foundation
- FastAPI backend serving chat and static frontend
- WebSocket streaming chat endpoint (`/ws/chat`)
- LLM router supporting Ollama (local), Claude (Anthropic), and OpenAI — provider-agnostic, single `.env` change to switch
- Vanilla JS frontend with Tailwind CDN — dark mode, streaming token display with blinking cursor
- In-session conversation history (replaced by SQLite in v0.4)
- `GET /health` endpoint
- `config.yaml` system — gitignored, copied from `config.yaml.example` at setup
- `run.py` entry point
- `.gitignore` excluding config, data, venv, and cache
