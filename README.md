# Personal Assistant

A self-hosted AI assistant that runs on your local machine. Accessible from any device on your network via browser — chat by text or voice. Fully local by default (no cloud costs), with optional Claude/OpenAI routing for quality tasks.

## Features

- **Chat UI** — browser-based, accessible from desktop, laptop, or phone; markdown rendering, message timestamps, export to Markdown
- **Voice input** — push-to-talk via browser mic on any device (faster-whisper STT + Kokoro TTS, both local)
- **Streaming responses** — tokens stream in real time with a stop button to cancel mid-response
- **LLM routing** — Ollama (local/free) by default; optional Claude, OpenAI, Gemini, or Groq selectable at runtime
- **Persistent memory** — remembers facts across conversations via ChromaDB; view and delete memories at `/memories`
- **Morning briefings** — weather, calendar, news digest, email summary, and reminders delivered daily
- **Reminders** — set reminders via chat or the `/reminders` page; snooze (15m/1h/tomorrow); fires ntfy push + browser notification when due
- **Proactive follow-ups** — if you mention a future commitment in chat ("I need to call the dentist"), the assistant quietly saves it as a reminder
- **Weekly digest** — automated weekly wrap-up (completed tasks, open reminders, news) via ntfy
- **Push notifications** — reminders via ntfy to phone or browser
- **Smart home** — Govee light control via chat (on/off, brightness, color, color temperature)
- **Email** — unread emails ranked by importance surfaced in the home dashboard and chat
- **Activity tracking** — passive Windows browser/app activity logged as context; Mac agent syncs via iCloud
- **Work session history** — ask "what did I work on last week?" and the assistant reads your Claude Code session files
- **Multi-chat** — full conversation history, per-chat rename/archive/pin/delete, sidebar search, and edit sent messages
- **Quick chat** — type a message on the home page and go straight into a new conversation
- **Document reading** — paste or attach a PDF/text file in chat; content injected as context (up to 12k chars)
- **Recurring reminders** — set daily, weekly, weekday, or custom-interval reminders; auto-requeued after firing
- **Calendar write** — create calendar events from chat via CalDAV
- **Code highlighting** — syntax-highlighted code blocks in assistant responses via highlight.js
- **Runtime config editing** — update config values (news topics, city, etc.) through chat without restarting

## Requirements

- Windows 10/11 (runs natively — no WSL required)
- Python 3.11+
- [Ollama](https://ollama.com) installed and running
- A pulled Ollama model (e.g. `ollama pull llama3.1:8b`)

## Setup

### 1. Clone the repo

```powershell
git clone https://github.com/alexjustdoit/personal-assistant.git
cd personal-assistant
```

### 2. Create and activate a virtual environment

```powershell
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Pull your Ollama model

```powershell
ollama pull llama3.1:8b
```

### 5. Start the assistant

```powershell
python run.py
```

Open `http://localhost:8000` in your browser. On first launch (no `config.yaml` present), you'll be redirected to the in-browser setup wizard automatically. Fill in your options across the steps — the wizard saves your config and restarts the server when done.

To reconfigure, delete `config.yaml` and restart — the wizard will run again.

To access from another device on your network (laptop, phone), open `http://<your-desktop-ip>:8000`.

### Getting your iCal URL (for calendar integration)

- **Google Calendar** — Settings → your calendar → *Secret address in iCal format*
- **Outlook** — Calendar Settings → Shared calendars → publish → copy ICS link
- **Apple Calendar** — Calendar → right-click calendar → Share Calendar → copy link

## Windows Service (auto-start + gaming toggle)

Running as a Windows service means the assistant starts automatically on boot and runs in the background without a terminal window.

### Prerequisites

Install NSSM (one time):
```powershell
winget install nssm
```

### Install the service

In an Administrator PowerShell terminal, from the project root:
```powershell
.\service\install.ps1
```

The service (`PersonalAssistant`) will start immediately and auto-start on every boot.

### Gaming toggle

Stop the assistant before gaming, start it after. Double-click either file — they self-elevate to admin:

| File | Action |
|---|---|
| `service\game_on.bat` | Stop assistant (free up resources) |
| `service\game_off.bat` | Start assistant again |

Tip: right-click each `.bat` file → *Create shortcut* → move shortcuts to your desktop for one-click access.

### Remove the service

```powershell
.\service\uninstall.ps1
```

### Logs

Service logs are written to `data\logs\assistant.log` (5 MB rotation).

## Activity Tracking (Windows)

The assistant passively logs your browser activity and active window on Windows, then uses those logs as context — so you can ask things like *"what was I working on this afternoon?"* without manually telling it anything.

**What it tracks:**
- Recent visits in Chrome and Edge — aggregated by domain with visit counts and page titles
- The foreground window title at the time of each snapshot

**How it works:**

Every N minutes (default 30), the scheduler reads recent browser history from Chrome/Edge's local SQLite databases (safe to read while the browser is open — it copies the file first), samples the active window via the Windows API, and writes a markdown snapshot to your configured log folder. At the configured end-of-day time (default 10pm), all that day's snapshots are synthesized into a single summary note via the LLM.

Both the individual snapshots and the daily summary are picked up by the notes watcher and made searchable.

**Configuration (`config.yaml`):**

```yaml
activity_tracking:
  enabled: true
  log_folder: "C:\\Users\\you\\Notes\\activity"   # created automatically if it doesn't exist
  poll_interval_minutes: 30
  eod_summary_time: "22:00"
  ignored_domains:          # exclude noisy or private domains
    - mail.google.com
    - linkedin.com
```

> You can also tell the assistant to ignore a domain via chat: *"stop logging LinkedIn"* or *"ignore reddit.com"*. It takes effect immediately and retroactively removes that domain from existing log files.

**`notes_folders` — what it's for:**

`notes_folders` is the list of directories the assistant watches and indexes for context. Add the activity log folder here so the assistant can search it. You can also add other personal notes folders (markdown or plain text files).

```yaml
notes_folders:
  - "C:\\Users\\you\\Notes\\activity"   # activity logs (add this one at minimum)
  - "C:\\Users\\you\\Notes\\personal"   # optional: your own notes
```

All folders are created automatically if they don't exist. Keep this list narrow — pointing it at a broad directory like Documents will ingest everything recursively.

## Multi-Computer Activity Tracking

The assistant runs on Windows, but you can feed it context from other machines on your network. Activity logs from other computers are picked up automatically and made available to the assistant as context — so it knows what you've been working on across devices.

### Mac Activity Agent

The mac-agent runs on any Mac on your network and logs browser activity and the active application every 30 minutes. Logs are written to iCloud Drive, which syncs them to Windows where the assistant picks them up automatically.

**What it tracks:**
- Recent visits across Safari, Chrome, and Edge — aggregated by domain with visit counts and page titles
- The frontmost application at the time of the snapshot

**How it works:**

```
Mac (launchd, every 30 min)
  → reads Safari + Chrome + Edge history (SQLite)
  → queries active app via AppleScript
  → writes markdown snapshot to iCloud Drive (PA-Activity/)
    → iCloud syncs to Windows
      → personal assistant ingests it as context
```

**Setup (Mac):**

```bash
cd mac-agent
cp config.yaml.example config.yaml
# Edit config.yaml — set log_folder to your iCloud Drive PA-Activity path
pip3 install pyyaml
chmod +x install.sh && ./install.sh
```

Grant **Full Disk Access** to Terminal in System Settings → Privacy & Security → Full Disk Access. This is required to read Safari history. Chrome and Edge work without it.

**Configuration (`mac-agent/config.yaml`):**

```yaml
log_folder: ~/Library/Mobile Documents/com~apple~CloudDocs/PA-Activity
poll_interval_minutes: 30
ignored_domains:        # optional — exclude noisy or private domains
  - mail.google.com
  - linkedin.com
```

**Manual run:**
```bash
python3 mac-agent/agent.py
```

**View agent logs:**
```bash
tail -f /tmp/pa-mac-agent.log
```

**Uninstall:**
```bash
./mac-agent/uninstall.sh
```

## LLM Routing

By default all requests go to Ollama (free, local). To use Claude or OpenAI:

1. Add your API key to `config.yaml`
2. Set `llm.quality_model` to `claude` or `openai`

A provider dropdown appears in the top-right of the UI, letting you switch models at runtime without touching config. Only providers with a configured API key are shown — a fresh install with no API keys shows Ollama only.

Quality routing is used for tasks that need higher accuracy (Phase 4+). Normal chat uses whichever provider is selected in the UI.

## Govee Smart Home

Control Govee lights by talking to the assistant — e.g. *"turn off the bedroom light"*, *"set the strip to purple"*, *"dim everything to 30%"*.

### Compatible devices

Any Govee device that appears in the **Govee Developer API v1** is supported. This covers WiFi-enabled lights — most light strips, bulbs, floor lamps, table lamps, and LED panels. **BLE-only devices are not supported** (they never appear in the API).

### Supported controls

| Control | What you can say | Device requirement |
|---|---|---|
| On / Off | "turn on the desk lamp", "turn everything off" | All WiFi devices |
| Brightness | "set brightness to 40%", "dim the strip" | Devices with `brightness` in `supportCmds` |
| Color (RGB) | "set to red", "change the strip to teal" | Devices with `color` in `supportCmds` |
| Color temperature | "warmer light", "set to 3000K" | Devices with `colorTem` in `supportCmds` |

Color names understood: red, green, blue, white, warm white, cool white, yellow, orange, purple, pink, cyan, teal, magenta, indigo, lavender, lime, coral, turquoise. Raw `r,g,b` values also work (e.g. "255,100,0").

You can target devices by name ("the bedroom light") or say "all" / "all lights" / "everything" to broadcast to all devices.

### Setup

1. Get a free API key at [developer.govee.com](https://developer.govee.com)
2. Add it to `config.yaml`:
   ```yaml
   govee:
     api_key: your-api-key-here
   ```
3. Restart the assistant.

> **Rate limit:** The free Developer API tier allows ~100 requests/day. The device list is cached for 1 hour to minimize API calls — each control action consumes one request.

## Email

Fetch unread emails from any IMAP server (Gmail, Outlook, etc.) and surface them in the home dashboard and via chat.

### Setup

Add accounts to `config.yaml`:

```yaml
email:
  fetch_hours: 24        # look back this many hours for unread mail
  max_per_account: 20
  accounts:
    - server: imap.gmail.com
      port: 993
      username: you@gmail.com
      password: your-app-password   # Gmail: use an App Password, not your main password
    - server: outlook.office365.com
      port: 993
      username: you@outlook.com
      password: your-password
```

**Gmail App Password:** Google Account → Security → 2-Step Verification → App passwords. Generate one for "Mail".

Emails are ranked by importance (reply chains, urgency keywords, personal sender, recency) before display. Only unread emails are fetched.

## Personal Memory

The assistant remembers facts across all conversations. Ask it to remember something explicitly, or it will extract facts automatically from your messages in the background.

To view and delete what it knows about you, go to `/memories` (brain icon in the home header).

## Work Session History

If you use Claude Code, the assistant can answer questions about your past work sessions — "what did I work on last week?", "what's the status of TAM Copilot?" — by reading `~/.claude/sessions/*.md` automatically.

No configuration needed if your session files are in the default location.

## Project Structure

```
personal-assistant/
├── backend/
│   ├── main.py               # FastAPI app — all HTTP routes
│   ├── config.py             # Config loader
│   ├── routers/
│   │   ├── chat.py           # WebSocket chat endpoint + intent detection
│   │   └── voice.py          # STT / TTS endpoints
│   └── services/
│       ├── llm.py            # LLM router (Ollama / Claude / OpenAI / Gemini / Groq)
│       ├── memory.py         # Conversation history, ChromaDB memory, reminders, chat management
│       ├── briefing.py       # Morning/evening briefing assembly + LLM narration
│       ├── scheduler.py      # APScheduler (briefing cron, reminder checks, weekly digest)
│       ├── notification_queue.py  # In-process queue for browser reminder notifications
│       ├── email_service.py  # IMAP email fetching + importance ranking
│       ├── activity_tracker.py  # Windows browser/app activity logger
│       ├── notes_watcher.py  # Watchdog file watcher for notes folders
│       ├── claude_memory.py  # Claude Code memory file indexer
│       ├── sessions_reader.py   # Reads ~/.claude/sessions/*.md for work history queries
│       ├── govee.py          # Govee Developer API client
│       ├── todoist.py        # Todoist REST API client
│       ├── weather.py        # OpenWeatherMap
│       ├── news.py           # RSS news fetcher + LLM synthesis
│       ├── calendar_service.py  # iCal URL parser
│       ├── search.py         # Tavily web search
│       ├── stt.py            # Speech-to-text (faster-whisper)
│       ├── tts.py            # Text-to-speech (Kokoro)
│       └── notifications.py  # ntfy push notifications
├── frontend/
│   ├── home.html             # Dashboard (briefing, quick-chat, sidebar)
│   ├── chat.html             # Chat view with collapsible sidebar
│   ├── memories.html         # Personal memory viewer (/memories)
│   ├── reminders.html        # Reminders page (/reminders)
│   ├── settings.html         # Settings editor (/settings)
│   ├── setup.html            # First-run setup wizard
│   ├── css/style.css
│   └── js/
│       ├── home.js
│       ├── chat.js
│       ├── memories.js
│       ├── reminders.js
│       ├── settings.js
│       └── setup.js
├── mac-agent/                # Mac activity tracker (feeds context via iCloud)
│   ├── agent.py              # Polls browser history + active app, writes markdown logs
│   ├── config.yaml.example
│   ├── install.sh            # Installs as a launchd job
│   └── uninstall.sh
├── data/                     # gitignored — conversations, memory, chroma DB
├── tests/                    # pytest test suite (run with: pytest)
├── run.py                    # Start the server
├── config.yaml.example       # Reference config
├── pytest.ini                # Test config
└── requirements.txt
```

## Running Tests

```powershell
pip install pytest
pytest
```

65 tests covering scheduler recurrence logic, memory service (SQLite), chat JSON parsing, briefing helpers, notification queue, and activity tracker.

## Data & Resetting

All runtime data lives in `data/` (gitignored — never pushed to the repo).

| Path | Contains |
|---|---|
| `data/conversations.db` | Chat history + reminders |
| `data/chroma/` | Personal memory (ChromaDB vectors) |
| `data/logs/` | Service logs |

**Full reset** (conversations, memory, briefings):
```powershell
rmdir /s /q data
```

**Reset and re-run setup wizard:**
```powershell
rmdir /s /q data
del config.yaml
```
Restart the server — you'll be redirected to the setup wizard automatically.

**Reset selectively:**
```powershell
del data\conversations.db     # clears chat history and reminders only
rmdir /s /q data\chroma       # clears personal memory only
```

The app recreates `data/` automatically on next start.

## Roadmap

- [x] Phase 1 — Chat UI, streaming, LLM routing
- [x] Phase 2 — Voice (faster-whisper STT, Kokoro TTS)
- [x] Phase 3 — Persistent memory (ChromaDB + memory management UI)
- [x] Phase 4 — Proactive layer (briefings, reminders, calendar, news, email)
- [x] Phase 5 — Onboarding wizard (in-browser setup, home page, multi-chat sidebar)
- [x] Phase 6 — Windows service (auto-start, gaming toggle)
- [x] Phase 7 — Smart home (Govee lights), Todoist tasks, image understanding
- [x] Phase 8 — Activity tracking (Windows + Mac agent via iCloud), notes watcher, Claude Code memory
- [x] Phase 9 — Chat polish (markdown, timestamps, stop button, export, archive, quick-chat, work history query)
- [x] Phase 10 — Reminders UI, weekly digest, settings page, browser notifications, memory management
- [x] Phase 11 — Calendar write (CalDAV), document/PDF reading, home quick-tiles, recurring reminders, code highlighting, runtime config editing, keyboard shortcuts
- [x] Phase 12 — Edit messages, SW background notifications, pin chats, reminder filter, inline memory editing, context badge, Todoist complete from home, stream error recovery, calendar read in chat, notification deep-links, quick-add reminder on home
- **v1.0** ✓
