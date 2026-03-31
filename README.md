# Personal Assistant

A self-hosted AI assistant that runs on your local machine. Accessible from any device on your network via browser — chat by text or voice. Fully local by default (no cloud costs), with optional Claude/OpenAI routing for quality tasks.

## Features

- **Chat UI** — browser-based, accessible from desktop, laptop, or phone
- **Voice input** — push-to-talk via browser mic on any device
- **Streaming responses** — tokens stream in real time
- **LLM routing** — Ollama (local/free) by default, optional Claude or OpenAI for quality tasks
- **Provider selector** — switch between LLMs at runtime via dropdown in the UI
- **Persistent memory** — remembers context and things you tell it *(Phase 3)*
- **Morning briefings** — weather, calendar, and news digest delivered daily *(Phase 4)*
- **Push notifications** — reminders via ntfy to phone or browser *(Phase 4)*
- **Smart home** — Govee light control via chat (on/off, brightness, color, color temperature)

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

## Project Structure

```
personal-assistant/
├── backend/
│   ├── main.py               # FastAPI app entry point
│   ├── config.py             # Config loader
│   ├── routers/
│   │   ├── chat.py           # WebSocket chat endpoint
│   │   └── voice.py          # STT / TTS endpoints
│   └── services/
│       ├── llm.py            # LLM router (Ollama / Claude / OpenAI)
│       ├── memory.py         # Conversation history + ChromaDB personal memory
│       ├── stt.py            # Speech-to-text (faster-whisper)
│       ├── tts.py            # Text-to-speech (Kokoro)
│       ├── weather.py        # OpenWeatherMap
│       ├── news.py           # Tavily news search
│       ├── calendar_service.py  # iCal URL parser
│       ├── notifications.py  # ntfy push notifications
│       ├── briefing.py       # Morning briefing assembly
│       └── scheduler.py      # APScheduler (briefing + reminders)
├── frontend/
│   ├── home.html             # Landing page (greeting, briefing, recent chats)
│   ├── chat.html             # Chat view with sidebar
│   ├── setup.html            # First-run setup wizard
│   ├── css/style.css
│   └── js/
│       ├── home.js
│       ├── chat.js
│       └── setup.js
├── mac-agent/                # Mac activity tracker (feeds context via iCloud)
│   ├── agent.py              # Polls browser history + active app, writes markdown logs
│   ├── config.yaml.example   # Config template (log_folder, poll_interval, ignored_domains)
│   ├── install.sh            # Installs as a launchd job (runs every N minutes)
│   └── uninstall.sh
├── data/                     # gitignored — conversations, memory, chroma DB
├── run.py                    # Start the server
├── config.yaml.example       # Reference config (copy to config.yaml)
└── requirements.txt
```

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
- [x] Phase 3 — Persistent memory (ChromaDB)
- [x] Phase 4 — Proactive layer (briefings, reminders, calendar, news)
- [x] Phase 5 — Onboarding wizard (in-browser setup, home page, multi-chat sidebar)
- [x] Phase 6 — Windows service (auto-start, gaming toggle)
