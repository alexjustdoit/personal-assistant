#!/usr/bin/env python3
"""First-run setup wizard for Home Assistant."""

import sys
import yaml
import getpass
from pathlib import Path

CONFIG_PATH = Path("config.yaml")

COMMON_TIMEZONES = [
    "America/New_York", "America/Chicago", "America/Denver",
    "America/Los_Angeles", "Europe/London", "Europe/Paris",
    "Europe/Berlin", "Asia/Tokyo", "Asia/Shanghai", "Australia/Sydney",
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def header(title):
    print(f"\n{'─' * 52}")
    print(f"  {title}")
    print(f"{'─' * 52}")


def ask(prompt, default=None, secret=False):
    suffix = f" [{default}]" if default is not None else ""
    full_prompt = f"  {prompt}{suffix}: "
    if secret:
        value = getpass.getpass(full_prompt)
    else:
        try:
            value = input(full_prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSetup cancelled.")
            sys.exit(0)
    return value if value else default


def ask_bool(prompt, default=True):
    hint = "Y/n" if default else "y/N"
    try:
        value = input(f"  {prompt} [{hint}]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nSetup cancelled.")
        sys.exit(0)
    if not value:
        return default
    return value in ("y", "yes")


def ask_timezone(default="America/New_York"):
    print(f"\n  Common timezones:")
    for i, tz in enumerate(COMMON_TIMEZONES, 1):
        print(f"    {i:2}. {tz}")
    raw = ask("Timezone (number or IANA name)", default=default)
    if raw and raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(COMMON_TIMEZONES):
            return COMMON_TIMEZONES[idx]
    try:
        import pytz
        pytz.timezone(raw)
        return raw
    except Exception:
        print(f"  Warning: '{raw}' may not be a valid timezone. Using it anyway.")
        return raw


def test_ollama(url, model):
    try:
        import httpx
        res = httpx.get(f"{url}/api/tags", timeout=5)
        if res.status_code == 200:
            models = [m["name"] for m in res.json().get("models", [])]
            if not models:
                print("  ⚠  Ollama is running but no models are pulled.")
                print(f"     Run: ollama pull {model}")
            elif not any(model.split(":")[0] in m for m in models):
                print(f"  ⚠  Model '{model}' not found. Available: {', '.join(models)}")
                print(f"     Run: ollama pull {model}")
            else:
                print(f"  ✓  Ollama connected. Model '{model}' is available.")
        else:
            print(f"  ✗  Ollama responded with status {res.status_code}.")
    except Exception:
        print(f"  ✗  Could not connect to Ollama at {url}.")
        print("     Make sure Ollama is running before starting the assistant.")


# ── Wizard sections ───────────────────────────────────────────────────────────

def setup_server():
    header("Server")
    port = ask("Port", default="8000")
    return {"host": "0.0.0.0", "port": int(port)}


def setup_llm():
    header("LLM")
    model = ask("Ollama model", default="llama3.1:8b")
    url = ask("Ollama URL", default="http://localhost:11434")
    print()
    test_ollama(url, model)

    quality_model = "ollama"
    anthropic_key = ""
    openai_key = ""
    openai_model = "gpt-4o-mini"

    print()
    if ask_bool("Add Anthropic API key for Claude quality routing?", default=False):
        anthropic_key = ask("Anthropic API key", secret=True) or ""
        if anthropic_key:
            quality_model = "claude"

    if ask_bool("Add OpenAI API key for GPT quality routing?", default=False):
        openai_key = ask("OpenAI API key", secret=True) or ""
        openai_model = ask("OpenAI model", default="gpt-4o-mini")
        if openai_key and quality_model == "ollama":
            quality_model = "openai"

    return {
        "llm": {
            "provider": "ollama",
            "model": model,
            "ollama_url": url,
            "quality_model": quality_model,
        },
        "anthropic_api_key": anthropic_key,
        "openai_api_key": openai_key,
        "openai_model": openai_model,
    }


def setup_voice():
    header("Voice")
    stt_enabled = ask_bool("Enable speech-to-text (STT)?", default=True)
    stt = {"enabled": stt_enabled}
    if stt_enabled:
        stt["model"] = ask("Whisper model size (tiny/base/small/medium/large-v3)", default="base")
        device = ask("Device (cuda/cpu)", default="cuda")
        stt["device"] = device
        stt["compute_type"] = "float16" if device == "cuda" else "int8"

    print()
    tts_enabled = ask_bool("Enable text-to-speech (TTS)?", default=True)
    tts = {"enabled": tts_enabled}
    if tts_enabled:
        print("  Voices: af_heart, af_bella, af_nicole, am_adam, am_michael")
        tts["voice"] = ask("Voice", default="af_heart")
        tts["speed"] = float(ask("Speed (0.5–2.0)", default="1.0"))

    return {"stt": stt, "tts": tts}


def setup_briefing():
    header("Morning Briefing")
    enabled = ask_bool("Enable morning briefing?", default=True)
    if not enabled:
        return {"briefing": {"enabled": False}}
    time_str = ask("Briefing time (24hr, e.g. 07:00)", default="07:00")
    timezone = ask_timezone()
    return {"briefing": {"enabled": True, "time": time_str, "timezone": timezone}}


def setup_weather():
    header("Weather  (OpenWeatherMap — free tier)")
    enabled = ask_bool("Enable weather in briefing?", default=True)
    if not enabled:
        return {"weather": {"enabled": False}}
    print("  Get a free key at https://openweathermap.org/api")
    api_key = ask("OpenWeatherMap API key", secret=True) or ""
    city = ask("City (e.g. New York,US)", default="") or ""
    units = ask("Units (imperial °F / metric °C)", default="imperial")
    return {"weather": {"enabled": bool(api_key and city), "api_key": api_key, "city": city, "units": units}}


def setup_calendar():
    header("Calendar  (iCal URL — works with Google, Outlook, Apple)")
    enabled = ask_bool("Enable calendar in briefing?", default=False)
    if not enabled:
        return {"calendar": {"enabled": False, "ical_url": ""}}
    print("  Google: Calendar Settings → your calendar → 'Secret address in iCal format'")
    print("  Outlook: Calendar Settings → Shared calendars → publish → copy ICS link")
    ical_url = ask("iCal URL") or ""
    return {"calendar": {"enabled": bool(ical_url), "ical_url": ical_url}}


def setup_news():
    header("News  (Tavily — free tier, 1000 searches/month)")
    enabled = ask_bool("Enable news digest in briefing?", default=True)
    if not enabled:
        return {"news": {"enabled": False, "api_key": "", "topics": []}}
    print("  Get a free key at https://tavily.com")
    api_key = ask("Tavily API key", secret=True) or ""
    raw_topics = ask("Topics (comma-separated, e.g. technology, Formula 1)") or ""
    topics = [t.strip() for t in raw_topics.split(",") if t.strip()]
    return {"news": {"enabled": bool(api_key and topics), "api_key": api_key, "topics": topics}}


def setup_notifications():
    header("Notifications  (ntfy — free, no account needed)")
    print("  Install the ntfy app on your phone, then subscribe to your topic.")
    print("  Pick any unique topic name — treat it like a password.")
    topic = ask("ntfy topic name (e.g. home-assistant-abc123)") or ""
    url = ask("ntfy server URL", default="https://ntfy.sh")
    return {"notifications": {"ntfy_url": url, "ntfy_topic": topic}}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 52)
    print("  Home Assistant — Setup Wizard")
    print("=" * 52)
    print("\nThis wizard creates your config.yaml.")
    print("Press Enter to accept default values shown in [brackets].")
    print("API keys are not stored in git — config.yaml is gitignored.")

    if CONFIG_PATH.exists():
        print(f"\n  ⚠  config.yaml already exists.")
        if not ask_bool("Overwrite it?", default=False):
            print("Setup cancelled. Your existing config.yaml was not changed.")
            sys.exit(0)

    cfg = {}

    server = setup_server()
    llm_section = setup_llm()
    voice = setup_voice()
    briefing = setup_briefing()
    weather = setup_weather()
    calendar = setup_calendar()
    news = setup_news()
    notifications = setup_notifications()

    cfg["server"] = server
    cfg["llm"] = llm_section["llm"]
    cfg.update(voice)
    cfg.update(briefing)
    cfg.update(weather)
    cfg.update(calendar)
    cfg.update(news)
    cfg.update(notifications)
    cfg["anthropic_api_key"] = llm_section["anthropic_api_key"]
    cfg["openai_api_key"] = llm_section["openai_api_key"]
    cfg["openai_model"] = llm_section["openai_model"]

    print(f"\n{'─' * 52}")
    CONFIG_PATH.write_text(yaml.dump(cfg, default_flow_style=False, sort_keys=False))
    print(f"  ✓  config.yaml saved.")
    print(f"\n{'=' * 52}")
    print("  Setup complete!")
    print(f"{'=' * 52}")
    print("\n  Start the assistant:")
    print("    python run.py")
    print()


if __name__ == "__main__":
    main()
