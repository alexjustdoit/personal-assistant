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
- **Smart home** — Govee and other integrations *(Phase 2)*

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

## LLM Routing

By default all requests go to Ollama (free, local). To use Claude or OpenAI:

1. Add your API key to `config.yaml`
2. Set `llm.quality_model` to `claude` or `openai`

A provider dropdown appears in the top-right of the UI, letting you switch models at runtime without touching config. Only providers with a configured API key are shown — a fresh install with no API keys shows Ollama only.

Quality routing is used for tasks that need higher accuracy (Phase 4+). Normal chat uses whichever provider is selected in the UI.

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
