# Changelog

All notable changes to this project are documented here.

---

## [Proposed]

### Next up

- **Test isolation** — fix `test_chat_parsing.py` `sys.modules` bleed when all test files are collected together (`conftest.py` or `--import-mode=importlib`)
- **v1.0 checklist** — define threshold and remaining gaps

---

## [0.20] — 2026-03-31

### Added — Calendar read in chat
- User can ask "what's on my calendar?" and the assistant reads upcoming events from all configured iCal sources and injects them as context

### Added — Multi-task creation
- `add_many` Todoist intent: LLM can detect a list of tasks in a single message and create them all in one shot
- Greedy JSON regex fix (`\{.*\}`) applied to all `_detect_*` functions — was `\{.*?\}` (non-greedy), which broke nested arrays like `add_many`

### Added — Notification click opens app
- Clicking an ntfy/browser notification now deep-links into the app (chat or reminders page as appropriate) via `notificationclick` handler in `sw.js`

### Added — Expandable context badge
- Context badge in chat header shows which sources were injected (memory, calendar, notes, etc.) for the last message; click to expand the full list

### Added — Pinned chats on home
- Pinned chats appear in a dedicated section at the top of the home page recent chats list

### Added — Quick-add reminder on home
- Reminder quick-add input directly on the home page (no need to navigate to `/reminders`)

### Fixed — Archive filter in get_chats()
- `GROUP BY m.session_id AND (condition)` was silently broken; corrected to proper `HAVING COALESCE(cn.archived,0)=0`

---

## [0.19] — 2026-03-31

### Added — Stream error recovery
- If the WebSocket drops mid-stream, the frontend reconnects and replays the partial response; no lost tokens

### Added — Todoist complete from home tile
- "Done" button on each task in the home tasks tile marks it complete via Todoist API without leaving the home page

### Added — Pin chats
- Pin/unpin any chat from the sidebar; pinned chats float to the top of both the home and chat sidebars
- `PATCH /api/chats/{session_id}` extended to accept `{pinned: true/false}`
- `pin_chat()` / `unpin_chat()` in `memory_service`

### Added — Reminder filter
- Search/filter input on `/reminders` page; filters the visible list client-side in real time against `_allReminders` array

### Added — Inline memory editing
- Click any memory on `/memories` to edit the text in place; `PATCH /api/memories/{id}` saves the updated text
- `update_memory_text()` in `memory_service`

### Added — Context badge
- Chat header badge showing how many context items (memories, notes, calendar, etc.) were injected into the last message; pulses briefly on each new injection

---

## [0.18] — 2026-03-31

### Added — Edit message
- Click any sent user message to edit it inline; submitting re-sends from that point and trims subsequent history

### Added — Service worker background notifications
- Reminder notifications now fire via the service worker even when the tab is in the background or the screen is locked

### Added — Email accounts in settings
- Email accounts (IMAP server, port, username, password) now editable from `/settings` without re-running the setup wizard

---

## [0.17] — 2026-03-31

### Added — Code syntax highlighting
- Code blocks in assistant responses are highlighted via highlight.js (injected after `finishStreaming()`)

### Added — Keyboard shortcuts
- `Ctrl+Enter` / `Cmd+Enter` — send message
- `Ctrl+K` — focus search in sidebar
- `Escape` — clear sidebar search / close modals

### Added — CalDAV test button
- "Test connection" button in the CalDAV section of settings; hits the configured CalDAV URL and reports success or auth error

### Added — Recurring reminders
- Reminders now support recurrence: daily, weekly, weekdays, or custom interval
- `recurrence` TEXT column in reminders table (automatic migration on startup)
- `_next_occurrence()` helper in scheduler; after a recurring reminder fires, it re-queues itself for the next due time

### Added — Runtime config editing via chat
- Say "change my news topics to tech and science" or "update my city to Seattle" — assistant detects config-edit intent, mutates the module-level config dict in place, and calls `save_config()` to write YAML; no restart required

---

## [0.16] — 2026-03-31

### Added — Home quick-tiles
- Calendar and tasks tiles on the home page load independently at page init via `loadQuickTiles()`; 5-minute auto-refresh; separate from the morning briefing

### Added — CalDAV calendar write
- Create calendar events from chat: "schedule a meeting with Sarah on Friday at 2pm"
- `calendar_service.py` `create_event()` method — CalDAV PUT using httpx + icalendar library
- `caldav_url`, `caldav_username`, `caldav_password` config keys under `config.calendar`

### Added — Document / PDF reading
- Paste or attach a document (PDF, .txt, .md) in chat; text extracted and injected into the system prompt (up to 12k chars)
- `POST /api/upload/document` — pypdf for PDFs, plain read for text files

---

## [0.15] — 2026-03-31

### Added — Copy & Regenerate on messages
- **Copy button** appears on hover for all assistant messages (history and fresh responses) — uses Clipboard API, shows "Copied!" briefly
- **Regenerate button** appears on hover for freshly streamed responses — deletes the last assistant turn from DB, removes it from the UI, re-sends the same user message with `regenerate: true` flag
- Backend handles `regenerate: true`: pops the stale assistant from in-memory history, skips re-saving the user message, streams a fresh response

### Added — Conversation summarization
- When history reaches 40 messages, the oldest 20 are compressed into a `role='summary'` row in the DB via `MemoryService.compress_messages()`
- Summary is loaded each message turn and injected into the system prompt as "Summary of earlier conversation" context
- `get_history()` now filters out `role='summary'` rows so they never appear in chat UI or history endpoints

### Added — Todoist project support
- LLM detection now extracts an optional `"project"` field from task-add intents (e.g. "add this to my Work project")
- `get_projects()` fetches all Todoist projects; matched by case-insensitive substring
- `add_task()` now accepts `project_id`; resolved project name appears in the confirmation message

---

## [0.14] — 2026-03-31

### Added — Auto-title chats
- After the first assistant response in a new chat, the backend generates a short title (3-6 words) using the detection model in the background
- Title pushed to the client via `{"type": "title"}` WebSocket message — sidebar and header update instantly without a reload
- Only fires on the first exchange; skips if the chat already has a custom name

### Added — Weather forecast
- 3-day forecast row below current conditions on the home weather tile (Mon/Tue/Wed with emoji, high, low)
- `WeatherService.get_forecast()` — calls OWM 5-day/3-hour forecast endpoint, groups by day, skips today
- `GET /api/weather/forecast` endpoint; fetched independently in `onBriefingReady` and appended to the tile

### Added — Settings: voice, notes folders, detection model
- **Voice section** — STT (enabled, model size, device) and TTS (enabled, voice, speed) now configurable without re-running the setup wizard
- **Notes Folders section** — dynamic add/remove list of watched paths; syncs directly to `notes_folders` in config
- **Detection model field** — set a fast Ollama model (e.g. `llama3.2:3b`) for intent classification without changing the main chat model

---

## [0.13] — 2026-03-31

### Added — Reminder snooze
- Hover any reminder on `/reminders` to reveal a clock (snooze) button alongside delete
- Snooze options: 15 min, 1 hour, Tomorrow 9am — updates the due time in place without a page reload
- `PATCH /api/reminders/{id}` endpoint accepts `{due_time: ISO string}`
- `memory_service.update_reminder_due(id, due_time)` method

### Added — Proactive follow-up suggestions
- When a user message contains an implied future commitment ("I need to call the dentist", "I'll send that report") without explicitly asking for a reminder, the assistant automatically saves it as a pending reminder
- Uses `_FOLLOWUP_HINT` pattern + fast LLM extraction (detection model) to filter for genuine actionable commitments
- Skips if user already used an explicit "remind me / set a reminder" phrase (handled by existing reminder flow)
- Fires a browser notification confirming the reminder was captured

---

## [0.12] — 2026-03-31

### Added — Reminders page
- `/reminders` — dedicated page listing all pending reminders with quick-add form
- Reminders shown with relative time (overdue in red, upcoming in gray); full time displayed on each row
- Quick-add: text input + optional datetime-local picker + Add button; Enter key submits
- Mark complete (circle button) or delete (trash icon on hover) from the list
- Bell icon link to `/reminders` added to home page header

### Added — Weekly digest
- Scheduled weekly wrap-up via ntfy: completed reminders, still-pending items, past work sessions, and top news summaries — narrated as 2-3 warm sentences by the LLM
- Config: `briefing.weekly_enabled`, `briefing.weekly_day` (e.g. `sunday`), `briefing.weekly_time` (e.g. `09:00`)
- Settings page now includes a weekly digest toggle + day/time pickers in the Briefing section

---

## [0.11] — 2026-03-31

### Added — Archive chats
- Soft-archive any chat from the sidebar — hover to reveal archive icon (alongside rename/delete)
- Archived chats hidden from the main list; collapsible "Archived (n)" section at the bottom of both sidebars (home and chat)
- `PATCH /api/chats/{session_id}` extended to accept `{archived: true/false}` in addition to `{name}`
- `chat_names` table: added `archived INTEGER DEFAULT 0` column with automatic migration on startup

### Added — Memory management UI
- `/memories` page listing all personal facts stored in ChromaDB
- Facts sorted newest first with date; hover any row to reveal a delete button
- Instant delete without confirmation — deletes the ChromaDB vector by ID
- `GET /api/memories` — returns all stored memories with IDs and timestamps
- `DELETE /api/memories/{id}` — deletes a specific memory by ChromaDB ID
- Brain icon link to `/memories` added to home page header

### Added — Session/work history query in chat
- `backend/services/sessions_reader.py` reads `~/.claude/sessions/*.md` (per-project Claude Code session files)
- Keyword-scores session files against the query + recency; injects the top N excerpts into the system prompt
- Triggered when user asks things like "what did I work on last week?", "what's the status of TAM Copilot?", "what did we build last session?"
- No external API needed — reads local files

### Added — Setup wizard test buttons
- **Govee test** — "Test connection" button under Govee API key; hits Govee Developer API, reports device count; `POST /api/setup/test-govee`
- **Email test** — "Test first account" button under email section; does IMAP SSL login, reports success or error message; `POST /api/setup/test-email`

### Added — Home page quick-chat
- Persistent input bar at the bottom of the home page — type a message and hit Chat to open a new conversation with it pre-filled and auto-sent
- Uses `localStorage.pending_message` handoff: home stores it, chat.js reads + clears + sends after socket opens
- Avoids flicker/double-send — polls until WebSocket is open before sending

### Added — Independent reminders tile
- `GET /api/reminders` endpoint returns all pending reminders (globally, not session-scoped)
- `loadRemindersTile()` in home.js fetches and renders reminders independently of the briefing — always up to date after briefing loads

---

## [0.10] — 2026-03-31

### Added — Markdown rendering in chat
- `marked.js` (v9) added to chat.html — renders assistant responses as HTML
- During streaming: textContent used for performance; on `finishStreaming()`: full markdown parsed and rendered
- CSS: comprehensive markdown styles for headings, lists, blockquotes, code blocks, tables, links, horizontal rules

### Added — Message timestamps
- `get_history()` now returns `timestamp` field from SQLite
- `appendMessage()` accepts optional timestamp; renders below bubble in `text-gray-600`
- User messages stamped with `new Date()` on send; assistant messages stamped when `finishStreaming()` runs
- History load passes stored timestamps so all past messages show original time

### Added — Briefing badge on chat page
- Pulsing indigo dot appears on the Home link in the chat sidebar when a briefing is generating in the background
- `checkBriefingBadge()` polls `/api/briefing/status` on load and every 3s while status is "generating"

### Added — Chat export
- Export button in chat header (download icon) — fetches full history, formats as Markdown with labels and timestamps, triggers file download
- File named after the current chat title, e.g. `my-chat-title.md`

### Added — Email section in setup wizard
- Dynamic IMAP account blocks in step 3 — add/remove multiple accounts
- Fields: IMAP server, port (default 993), email address, password
- `buildConfig()` collects all account blocks into `email.accounts[]`, filtering blanks

---

## [0.9] — 2026-03-31

### Added — Email summarization
- `backend/services/email_service.py` — IMAP SSL client supporting multiple accounts (Gmail, Outlook, etc.)
- Fetches unread emails from the last N hours; importance-scored and ranked before display
- Importance scoring (heuristic, no LLM): reply chains (+0.35), urgency keywords (+0.25), personal sender (+0.25), short subject (+0.10), has body (+0.05), plus recency bias up to +0.5
- 15-minute cache (force-refresh available)
- Home page email tile: shows summary + up to 6 emails ranked by importance; refresh button
- Chat integration: email context injected into system prompt when "email/inbox/mail" detected in message
- `GET /api/email/summary?force=&provider=` endpoint

### Added — Stop button
- "Stop" button appears in chat footer while a response is streaming; "Send" is hidden
- Clicking Stop closes the WebSocket (triggers `WebSocketDisconnect` on the server, cancelling the Ollama stream), calls `finishStreaming()`, then reconnects immediately
- Server-side: no changes needed — WS disconnect is the cancellation signal

### Added — Delete and rename chats
- Hover any chat in either sidebar to reveal pencil (rename) and trash (delete) icons
- Inline rename: replaces name with a text input, saves on blur or Enter, cancels on Escape
- Delete: confirmation dialog, then `DELETE /api/chats/{session_id}` — if deleting the active chat, starts a new session
- `chat_names` SQLite table stores custom names; `get_chats()` uses `COALESCE(cn.name, first_user_message)`
- `DELETE /api/chats/{id}` and `PATCH /api/chats/{id}` API endpoints

### Added — Background briefing generation
- `POST /api/briefing/generate` returns immediately: if cached result exists returns it, otherwise kicks off `asyncio.create_task(_run_briefing(...))` and returns `{"status": "generating"}`
- `GET /api/briefing/status` returns current status or full result when ready
- Home page polls status every 2s when status is "generating" — navigating away no longer kills generation
- Module-level `_briefing_state` dict tracks status/result; resets on server restart

### Added — Chat search
- Search input in sidebar on both home and chat pages
- `GET /api/search?q=` does SQL LIKE across all messages; returns chat name, snippet, session ID
- 300ms debounce on input; Escape clears and restores chat list
- Clicking a result switches to that chat

### Added — Shared ignored domains sync (Windows ↔ Mac)
- `ignored_domains.txt` written to the iCloud log folder when a domain is ignored on Windows
- Mac agent reads the shared file in addition to its own config
- Domains stay in sync across machines without any networking

### Fixed — Windows config path documentation
- All path examples in `config.yaml.example` changed to forward slashes — work natively on Windows, no double-backslash confusion

---

## [0.8] — 2026-03-31

### Added — Notes watcher
- `backend/services/notes_watcher.py` — watchdog-based file watcher for local and iCloud folders
- Indexes `.md` and `.txt` files into a searchable in-memory store with TF-IDF-style scoring
- Relevant snippets injected into system prompt when content matches the user's query
- `notes_folders` config key: list of directories to watch

### Added — Windows passive activity tracker
- `backend/services/activity_tracker.py` — reads Chrome and Edge history SQLite DBs (copies before reading), samples active window via ctypes
- Runs every 30 minutes via APScheduler; writes markdown snapshots to configured log folder
- End-of-day LLM synthesis at configurable time (default 22:00) — summarises the day's snapshots into a single note
- Activity logs picked up automatically by notes_watcher and used as assistant context
- Chat command to ignore a domain: "stop logging LinkedIn" — detected by LLM, removes domain from existing logs retroactively
- `activity_tracking` config section with `enabled`, `log_folder`, `poll_interval_minutes`, `eod_summary_time`, `ignored_domains`

---

## [0.7] — 2026-03-31

### Added — Claude Code memory integration
- `backend/services/claude_memory.py` — watchdog watcher for Claude Code memory files (`~/.claude/projects/.../memory/*.md`)
- Indexed into ChromaDB alongside personal memories; injected into system prompt as "Context from Claude Code memory files"
- `claude_memory.path` config key points to the memory directory
- Allows the assistant to answer questions about Claude project context, user preferences, and past decisions captured by Claude Code's memory system

### Changed — Renamed to Personal Assistant
- Project renamed from "Home Assistant" to "Personal Assistant" throughout

---

## [0.6] — 2026-03-31

### Added — Govee smart home control
- `backend/services/govee.py` — Govee Developer API v1 client
  - Device list fetched once and cached in memory for 1 hour (conserves the ~100 req/day free tier limit)
  - `execute_govee_intent()` handles on, off, brightness, color, color_temp commands
  - `COLOR_MAP` maps natural language color names to RGB (red, blue, orange, purple, warm white, etc.)
  - `find_devices()` matches by partial device name; "all" targets every device
  - Graceful fallback if API unreachable — returns stale cache
- Chat integration: `_detect_govee()` runs in parallel with search and Todoist detection
  - Device names injected into the detect prompt so the LLM can match user phrasing to real devices
  - Supports: "turn on the lamp", "set the bedroom light to blue", "dim all lights to 30%", "warm white"
- `GET /api/govee/devices` endpoint — lists device names, models, controllable status
- Setup wizard: Govee API key field
- `config.yaml.example`: `govee.api_key` field added

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
