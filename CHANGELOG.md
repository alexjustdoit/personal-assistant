# Changelog

All notable changes to this project are documented here.

---

## [Proposed]

### Next up

- **Govee lights / smart home control** — Voice and chat control of Govee devices via Govee Developer API
- **Govee lights / smart home control** — Voice and chat control of Govee devices (bulbs, lamps, air purifier) via Govee Developer API; LLM intent detection routes commands to device actions
- **Email summarization** — Connect to Gmail/Outlook; summarize unread emails in briefing or on demand; spam filtering/cleanup step before surfacing to LLM; support multiple inboxes
- **Image understanding** — Allow image uploads or pastes in chat; route to vision-capable providers (Claude, Gemini) for analysis, document reading, error diagnosis

---

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

## [0.5] — 2026-03-31

### Added — Todoist integration
- `backend/services/todoist.py` — Todoist REST API v2 client: `get_tasks`, `add_task`, `complete_task`, `find_task_by_name`
- `GET /api/todoist/tasks` — returns today + overdue tasks for the home page tile
- Home page tasks tile: shows today/overdue tasks with due dates; refresh button; only appears when Todoist is configured
- Chat integration: LLM detects "add X to my list", "what's on my list", "I finished X" intents in parallel with web search detection; executes via Todoist API and injects confirmation/results into system prompt
- Setup wizard: Todoist API token field under Integrations
- `config.yaml.example`: `todoist.api_token` field added

### Added — Image understanding in chat
- Paste an image (Ctrl+V) or click the image button to attach a photo or screenshot
- Images are compressed to max 1024px via canvas before encoding — keeps WS payload small
- Image preview shown above input with remove button
- Routed to Claude (Haiku) or Gemini 2.0 Flash depending on which API keys are configured; Claude preferred
- Backend: `stream_vision()` method on LLMRouter; `_stream_claude_vision()` and `_stream_gemini_vision()` inject image into last user message in the appropriate format
- Shows descriptive error if no vision-capable provider is configured

---

## [0.4] — 2026-03-31

### Added — Web search in chat
- `backend/services/search.py` — Tavily API client (httpx, no new dependency); `web_search()` and `search_enabled()`
- Before each chat response, LLM classify call detects if current/real-time information is needed
- If yes: sends `{"type": "searching", "query": "..."}` WS event, runs Tavily search, injects top results into system prompt
- Frontend shows "Searching the web for '...'…" in the assistant bubble while search runs
- Zero overhead when no search needed; graceful fallback if Tavily key not set
- Tavily key stored in `news.api_key`; setup wizard label updated to mention chat search
- `config.yaml.example` updated with `api_key` under news section

### Added — Automatic memory extraction
- After each user message, a background task (`asyncio.create_task`) extracts implicit personal facts via LLM
- Saves preferences, relationships, habits, goals, and context automatically to ChromaDB — no "remember that" required
- Complements existing explicit memory detection; explicit phrases still take priority
- Extraction runs concurrently with the main response — zero latency impact

### Fixed — Session-scoped reminders
- Reminders are now fetched globally (not filtered by session ID) when building the system prompt
- A reminder set in one chat now appears as context in all future chats

---

## [0.3] — 2026-03-30

### Added — PWA / home screen install
- `manifest.json` with app name, theme color, and SVG icon
- `icon.svg` — custom house icon with indigo palette
- `sw.js` — minimal service worker (pass-through, no offline caching) enabling the install prompt
- `/sw.js` route in FastAPI serving the service worker at the correct scope
- PWA meta tags added to home.html and chat.html: manifest link, theme-color, apple-mobile-web-app tags
- Service worker registered on page load — browser will show "Add to Home Screen" / install prompt

### Added — Second calendar source
- `calendar_service.py` now reads `ical_urls` list from config (supports any number of sources)
- Backward compatible with legacy `ical_url` single-string config
- All URLs fetched in parallel via `asyncio.gather`
- Events merged and deduplicated by (title, start time) before sorting
- Setup wizard updated: "Calendar 1 / Calendar 2" fields with "+ Add second calendar" toggle
- `config.yaml.example` updated to `ical_urls: []` list format

### Added — Evening briefing
- `generate_and_send_briefing(period="morning")` now accepts a `period` parameter
- Evening briefing sends warm, reflective tone via `PERIOD_SYSTEM["evening"]`
- Saves to SQLite briefing cache — home page shows whichever briefing is most recent
- New `_run_evening_briefing` scheduler job reads `briefing.evening_enabled` + `briefing.evening_time`
- Setup wizard: "Evening briefing" toggle + time picker in Integrations step
- `config.yaml.example` updated with `evening_enabled: false` and `evening_time: "18:00"`

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
