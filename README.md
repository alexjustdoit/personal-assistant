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

### 5. Run the setup wizard

```powershell
python setup.py
```

The wizard walks through every configuration option — LLM, voice, briefing time, weather, calendar, news, and notifications. Press Enter to accept defaults. Your answers are saved to `config.yaml` (gitignored).

To reconfigure at any time, run `python setup.py` again.

### 6. Start the assistant

```powershell
python run.py
```

Open `http://localhost:8000` in your browser.

To access from another device on your network (laptop, phone), open `http://<your-desktop-ip>:8000`.

### Getting your iCal URL (for calendar integration)

- **Google Calendar** — Settings → your calendar → *Secret address in iCal format*
- **Outlook** — Calendar Settings → Shared calendars → publish → copy ICS link
- **Apple Calendar** — Calendar → right-click calendar → Share Calendar → copy link

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
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
├── data/                     # gitignored — conversations, memory, chroma DB
├── setup.py                  # First-run configuration wizard
├── run.py                    # Start the server
├── config.yaml.example       # Reference config (copy to config.yaml)
└── requirements.txt
```

## Roadmap

- [x] Phase 1 — Chat UI, streaming, LLM routing
- [x] Phase 2 — Voice (faster-whisper STT, Kokoro TTS)
- [x] Phase 3 — Persistent memory (ChromaDB)
- [x] Phase 4 — Proactive layer (briefings, reminders, calendar, news)
- [x] Phase 5 — Onboarding wizard
- [ ] Phase 6 — Windows service (auto-start, gaming toggle)
