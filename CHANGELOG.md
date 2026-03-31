# Changelog

All notable changes to this project are documented here.

---

## [Proposed]

### Smart home — Govee integration
Control Govee devices via the Govee Developer API. Planned device support (subject to API compatibility — verify at developer.govee.com):
- **H6008 smart bulbs** — on/off, brightness, color temperature (likely supported)
- **RGBIC Lyra floor lamp** — on/off, brightness, color/scene control (RGBIC support varies by model)
- **Govee Life Smart air purifier** — on/off, mode/fan speed (appliance API support uncertain)

Control via chat ("turn off the bedroom light", "set the lamp to red") using LLM intent detection and Govee API calls.

### UI quality of life
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

## [0.2] — 2026-03-30

### Added — In-browser setup wizard
- Multi-step setup wizard served at `/setup` (Welcome → AI Engine → Integrations → Voice → Launch)
- App boots without `config.yaml` — automatically redirects to `/setup` on first run
- Live Ollama connection test built into the wizard
- Config saved via `POST /api/setup/save`; server restarts automatically and wizard polls `/health` until it's back
- Replaces `setup.py` terminal wizard entirely

### Added — Home landing page
- `/` now serves a dashboard page (`home.html`) instead of going straight to chat
- Displays time-aware greeting (good morning / afternoon / evening) and today's date
- Morning briefing card — shows the most recent LLM-narrated briefing with timestamp
- Recent chats list — click any to jump straight into that conversation
- "New chat" button creates a fresh session

### Added — Chat sidebar & multi-chat
- Collapsible sidebar in chat view listing all past conversations
- Chats named automatically from first user message; sorted by most recently active
- Click any chat to switch — session ID stored in `localStorage`, history loaded on connect
- New Chat button in sidebar starts a fresh session
- Sidebar collapses on mobile (full-screen overlay with backdrop)
- Hamburger toggle in header on all screen sizes

### Changed — Backend
- `config.py` loads gracefully with no `config.yaml` (returns `{}` instead of crashing)
- `is_configured()` check gates scheduler startup and page routing
- `memory.py` — added `briefings` table, `save_briefing()`, `get_latest_briefing()`, `get_chats()`
- `briefing.py` — saves generated briefing to SQLite in addition to sending via ntfy
- `llm.py` — graceful init with missing config; uses `.get()` with defaults throughout
- `main.py` — multi-page routing (`/`, `/chat`, `/setup`), setup API endpoints, `os.execv` restart
- New endpoints: `GET /api/briefing/latest`, `GET /api/chats`, `POST /api/setup/test-ollama`

---

## [0.1] — 2026-03-30

### Added — Foundation
- FastAPI backend serving chat and static frontend
- WebSocket streaming chat endpoint (`/ws/chat`)
- LLM router supporting Ollama (local), Claude (Anthropic), and OpenAI — provider-agnostic, single env change to switch
- `GET /api/providers` endpoint — returns available providers based on configured API keys
- Provider dropdown in header — switch between LLMs at runtime without touching config
- Vanilla JS frontend with Tailwind CDN — dark mode, streaming token display with blinking cursor
- Welcome screen with suggestion chips — shown on first load, disappears once conversation starts
- `GET /health` endpoint
- `config.yaml` system — gitignored, copied from `config.yaml.example` at setup
- `run.py` entry point with helpful error if `config.yaml` is missing

### Added — Voice
- Speech-to-text via `faster-whisper` — runs locally on GPU, `base` model by default
- Text-to-speech via Kokoro TTS — local, free, near-API quality
- Sentence-level streaming TTS — audio begins playing after the first sentence rather than waiting for the full response
- `POST /api/voice/transcribe` — accepts browser audio blob, returns transcribed text
- `POST /api/voice/speak` — accepts text, returns WAV audio
- `GET /api/voice/status` — reports STT/TTS availability to frontend
- Mic button in UI — click to record, click to stop, pulses red while recording
- Speaker toggle in header — hides if TTS disabled in config; sending a new message stops current audio

### Added — Persistent Memory
- SQLite database (`data/conversations.db`) stores full conversation history and reminders per session
- ChromaDB vector store (`data/chroma/`) for semantic personal memory
- Session IDs generated in browser `localStorage`, passed as WebSocket query parameter
- Relevant memories retrieved on each message and injected into the system prompt automatically
- Explicit memory detection from chat: *"remember that..."*, *"note that..."*, *"don't forget..."*, *"keep in mind..."*
- Conversation history reloaded on page refresh
- `GET /api/history/{session_id}` endpoint
- `data/` directory gitignored — nothing personal ever touches the repo

### Added — Proactive Layer
- Morning briefing delivered via ntfy — weather, calendar events, news headlines, and reminders narrated by the LLM
- Weather via OpenWeatherMap API (free tier) — imperial or metric
- News digest via Tavily API — user-defined topics, up to 2 headlines each
- Calendar via iCal URL — works with Google Calendar, Outlook, and Apple Calendar without OAuth
- Reminders — detected from natural language in chat via LLM, stored in SQLite, due-time parsed via `dateparser`
- Push notifications via ntfy — reminder alerts and morning briefing delivery
- APScheduler background scheduler — cron job for morning briefing, 1-minute interval for reminder checks
- Pending reminders injected into system prompt so the assistant is aware of them conversationally

### Added — Onboarding & Service
- `setup.py` — interactive CLI wizard covering all config sections with live Ollama connection test
- `service/install.ps1` — installs app as `PersonalAssistant` Windows service via NSSM, auto-starts on boot
- `service/uninstall.ps1` — cleanly removes the service
- `service/game_on.bat` / `game_off.bat` — stop/start service for gaming, self-elevating to admin
- Service logs written to `data/logs/` with 5MB rotation
