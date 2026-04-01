import asyncio
import os
import sys
import yaml
import httpx
from pathlib import Path
from fastapi import FastAPI, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from backend.config import is_configured, CONFIG_PATH, config
from backend.routers import chat, voice

_briefing_state: dict = {"status": "idle", "result": None}

app = FastAPI(title="Personal Assistant")

frontend_path = Path(__file__).parent.parent / "frontend"


@app.on_event("startup")
async def startup():
    if is_configured():
        from backend.services.scheduler import scheduler_service
        scheduler_service.start()

        claude_mem_path = config.get("claude_memory", {}).get("path")
        if claude_mem_path:
            from backend.services.claude_memory import claude_memory_service
            claude_memory_service.start(claude_mem_path)

        notes_paths = config.get("notes_folders", [])
        if notes_paths:
            from backend.services.notes_watcher import notes_watcher_service
            notes_watcher_service.start(notes_paths)


@app.on_event("shutdown")
async def shutdown():
    if is_configured():
        try:
            from backend.services.scheduler import scheduler_service
            scheduler_service.stop()
        except Exception:
            pass
        try:
            from backend.services.notes_watcher import notes_watcher_service
            notes_watcher_service.stop()
        except Exception:
            pass


app.include_router(chat.router)
app.include_router(voice.router)

app.mount("/static", StaticFiles(directory=frontend_path), name="static")


# ── Page routes ───────────────────────────────────────────────────────────────

@app.get("/")
async def serve_home():
    if not is_configured():
        return RedirectResponse("/setup")
    return FileResponse(frontend_path / "home.html")


@app.get("/setup")
async def serve_setup():
    return FileResponse(frontend_path / "setup.html")


@app.get("/sw.js")
async def serve_sw():
    return FileResponse(frontend_path / "sw.js", media_type="application/javascript")


@app.get("/chat")
async def serve_chat():
    if not is_configured():
        return RedirectResponse("/setup")
    return FileResponse(frontend_path / "chat.html")


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "configured": is_configured()}


# ── Setup API ─────────────────────────────────────────────────────────────────

@app.post("/api/setup/save")
async def save_setup(request: Request):
    data = await request.json()
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    asyncio.create_task(_restart_after_delay())
    return {"status": "restarting"}


@app.post("/api/setup/test-ollama")
async def test_ollama(request: Request):
    data = await request.json()
    url = data.get("url", "http://localhost:11434")
    model = data.get("model", "")
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(f"{url}/api/tags", timeout=5)
            models = [m["name"] for m in res.json().get("models", [])]
            model_available = any(model.split(":")[0] in m for m in models)
            return {"connected": True, "model_available": model_available, "models": models}
    except Exception:
        return {"connected": False, "model_available": False, "models": []}


async def _restart_after_delay():
    await asyncio.sleep(2)
    os.execv(sys.executable, [sys.executable] + sys.argv)


# ── Data APIs ─────────────────────────────────────────────────────────────────

@app.get("/api/history/{session_id}")
async def get_history(session_id: str):
    from backend.services.memory import memory_service
    return {"messages": memory_service.get_history(session_id)}


@app.delete("/api/history/{session_id}/last")
async def delete_last_message(session_id: str, count: int = 1):
    from backend.services.memory import memory_service
    await asyncio.to_thread(memory_service.delete_last_messages, session_id, count)
    return {"ok": True}


@app.get("/api/chats")
async def get_chats(archived: str = "false"):
    from backend.services.memory import memory_service
    include_archived = archived.lower() == "true"
    return {"chats": memory_service.get_chats(include_archived=include_archived)}


@app.delete("/api/chats/{session_id}")
async def delete_chat(session_id: str):
    from backend.services.memory import memory_service
    await asyncio.to_thread(memory_service.delete_chat, session_id)
    return {"ok": True}


@app.patch("/api/chats/{session_id}")
async def rename_chat(session_id: str, request: Request):
    data = await request.json()
    name = (data.get("name") or "").strip()
    archived = data.get("archived")
    pinned = data.get("pinned")
    from backend.services.memory import memory_service
    if name:
        await asyncio.to_thread(memory_service.rename_chat, session_id, name)
    if archived is True:
        await asyncio.to_thread(memory_service.archive_chat, session_id)
    elif archived is False:
        await asyncio.to_thread(memory_service.unarchive_chat, session_id)
    if pinned is True:
        await asyncio.to_thread(memory_service.pin_chat, session_id)
    elif pinned is False:
        await asyncio.to_thread(memory_service.unpin_chat, session_id)
    return {"ok": True}


@app.get("/api/search")
async def search_chats(q: str = ""):
    if not q or len(q) < 2:
        return {"results": []}
    from backend.services.memory import memory_service
    results = await asyncio.to_thread(memory_service.search_messages, q)
    return {"results": results}


@app.get("/api/briefing/latest")
async def get_latest_briefing():
    from backend.services.memory import memory_service
    briefing = memory_service.get_latest_briefing()
    return briefing or {}


@app.post("/api/briefing/generate")
async def generate_briefing(request: Request):
    data = await request.json()
    period = data.get("period", "morning")
    if period not in ("morning", "afternoon", "evening", "night"):
        period = "morning"
    force = data.get("force", False)
    provider = data.get("provider") or None

    # Return cached result immediately if available and not forcing
    if not force and _briefing_state["status"] == "ready" and _briefing_state["result"]:
        return _briefing_state["result"]

    # Kick off background generation (idempotent — won't double-start)
    if _briefing_state["status"] != "generating":
        _briefing_state["status"] = "generating"
        _briefing_state["result"] = None
        asyncio.create_task(_run_briefing(period, force, provider))

    return {"status": "generating"}


async def _run_briefing(period: str, force: bool, provider: str | None):
    from backend.services.briefing import generate_on_demand_briefing
    try:
        result = await generate_on_demand_briefing(period, force=force, provider=provider)
        _briefing_state["status"] = "ready"
        _briefing_state["result"] = result
    except Exception as e:
        _briefing_state["status"] = "error"
        _briefing_state["result"] = None


@app.get("/api/briefing/status")
async def get_briefing_status():
    if _briefing_state["status"] == "ready" and _briefing_state["result"]:
        return _briefing_state["result"]
    return {"status": _briefing_state["status"]}


@app.get("/api/weather/forecast")
async def get_weather_forecast():
    from backend.services.weather import weather_service
    try:
        forecast = await weather_service.get_forecast()
        return {"forecast": forecast}
    except Exception:
        return {"forecast": []}


@app.get("/api/calendar/events")
async def get_calendar_events():
    from backend.services.calendar_service import calendar_service
    events = await calendar_service.get_events()
    return {"events": events}


@app.get("/api/govee/devices")
async def get_govee_devices():
    from backend.services.govee import get_devices, govee_enabled
    if not govee_enabled():
        return {"enabled": False, "devices": []}
    devices = await get_devices()
    return {"enabled": True, "devices": [{"name": d.get("deviceName", "?"), "model": d.get("model", "?"), "controllable": d.get("controllable", False)} for d in devices]}


@app.get("/api/todoist/tasks")
async def get_todoist_tasks():
    from backend.services.todoist import get_tasks, todoist_enabled
    if not todoist_enabled():
        return {"enabled": False, "tasks": []}
    tasks = await get_tasks("today | overdue")
    return {"enabled": True, "tasks": tasks}


@app.get("/api/email/summary")
async def get_email_summary(force: str = "false", provider: str = ""):
    from backend.services.email_service import email_enabled, fetch_emails, summarize_emails
    if not email_enabled():
        return {"enabled": False}
    emails = await fetch_emails(force=force.lower() == "true")
    summary = await summarize_emails(emails, provider=provider or None)
    account_counts = {}
    for e in emails:
        account_counts[e["account"]] = account_counts.get(e["account"], 0) + 1
    return {
        "enabled": True,
        "count": len(emails),
        "account_counts": account_counts,
        "summary": summary,
        "emails": [{"from": e["from"], "subject": e["subject"], "date": e["date"], "account": e["account"]} for e in emails[:10]],
    }


@app.get("/api/providers")
async def get_providers():
    from backend.services.llm import llm_router
    return {
        "providers": llm_router.available_providers(),
        "default": llm_router.default_provider_id,
    }


@app.get("/api/memories")
async def list_memories():
    from backend.services.memory import memory_service
    try:
        mems = await asyncio.to_thread(memory_service.list_memories)
        return {"memories": sorted(mems, key=lambda m: m.get("timestamp", ""), reverse=True)}
    except Exception:
        return {"memories": []}


@app.delete("/api/memories/{memory_id}")
async def delete_memory(memory_id: str):
    from backend.services.memory import memory_service
    await asyncio.to_thread(memory_service.delete_memory_by_id, memory_id)
    return {"ok": True}


@app.patch("/api/memories/{memory_id}")
async def update_memory(memory_id: str, request: Request):
    data = await request.json()
    text = (data.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "text required"}, status_code=400)
    from backend.services.memory import memory_service
    await asyncio.to_thread(memory_service.update_memory_text, memory_id, text)
    return {"ok": True}


@app.post("/api/todoist/tasks/{task_id}/complete")
async def complete_todoist_task(task_id: str):
    from backend.services.todoist import complete_task, todoist_enabled
    if not todoist_enabled():
        return JSONResponse({"error": "Todoist not configured"}, status_code=400)
    ok = await complete_task(task_id)
    return {"ok": ok}


@app.get("/api/reminders")
async def get_reminders():
    from backend.services.memory import memory_service
    reminders = await asyncio.to_thread(memory_service.get_pending_reminders)
    return {"reminders": reminders}


@app.post("/api/reminders")
async def create_reminder(request: Request):
    data = await request.json()
    text = (data.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "text required"}, status_code=400)
    due_time = data.get("due_time") or None
    recurrence = data.get("recurrence") or None
    from backend.services.memory import memory_service
    await asyncio.to_thread(memory_service.create_reminder, text, due_time, recurrence)
    return {"ok": True}


@app.patch("/api/reminders/{reminder_id}")
async def update_reminder(reminder_id: int, request: Request):
    data = await request.json()
    due_time = data.get("due_time")
    if due_time is not None:
        from backend.services.memory import memory_service
        await asyncio.to_thread(memory_service.update_reminder_due, reminder_id, due_time)
    return {"ok": True}


@app.post("/api/reminders/{reminder_id}/complete")
async def complete_reminder(reminder_id: int):
    from backend.services.memory import memory_service
    await asyncio.to_thread(memory_service.complete_reminder, reminder_id)
    return {"ok": True}


@app.delete("/api/reminders/{reminder_id}")
async def delete_reminder(reminder_id: int):
    from backend.services.memory import memory_service
    await asyncio.to_thread(memory_service.delete_reminder, reminder_id)
    return {"ok": True}


@app.get("/reminders")
async def serve_reminders():
    if not is_configured():
        return RedirectResponse("/setup")
    return FileResponse(frontend_path / "reminders.html")


@app.get("/api/notifications/pending")
async def get_pending_notifications():
    from backend.services.notification_queue import pop_all
    return {"notifications": pop_all()}


@app.get("/api/config")
async def get_config():
    """Return current config with secrets partially masked for the settings UI."""
    import copy
    cfg = copy.deepcopy(config)

    def mask(val: str) -> str:
        if not val or len(val) < 8:
            return val
        return val[:4] + "•" * (len(val) - 4)

    # Mask API keys / passwords
    for key in ("anthropic_api_key", "openai_api_key", "gemini_api_key", "groq_api_key"):
        if cfg.get(key):
            cfg[key] = mask(cfg[key])
    for section in ("govee", "todoist"):
        for field in ("api_key", "api_token"):
            if cfg.get(section, {}).get(field):
                cfg[section][field] = mask(cfg[section][field])
    for acct in cfg.get("email", {}).get("accounts", []):
        if acct.get("password"):
            acct["password"] = mask(acct["password"])

    return cfg


@app.post("/api/setup/test-govee")
async def test_govee(request: Request):
    data = await request.json()
    api_key = data.get("api_key", "").strip()
    if not api_key:
        return {"connected": False, "error": "No API key provided"}
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                "https://developer-api.govee.com/v1/devices",
                headers={"Govee-API-Key": api_key},
                timeout=10,
            )
            if res.status_code == 200:
                devices = res.json().get("data", {}).get("devices", [])
                return {"connected": True, "device_count": len(devices)}
            return {"connected": False, "error": f"HTTP {res.status_code}"}
    except Exception as e:
        return {"connected": False, "error": str(e)}


@app.post("/api/setup/test-caldav")
async def test_caldav(request: Request):
    data = await request.json()
    url = (data.get("url") or "").strip().rstrip("/")
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not url:
        return {"connected": False, "error": "No URL provided"}
    try:
        auth = (username, password) if username else None
        async with httpx.AsyncClient() as client:
            res = await client.request(
                "PROPFIND", url,
                headers={"Depth": "0", "Content-Type": "application/xml"},
                auth=auth,
                timeout=10,
            )
        if res.status_code in (200, 207):
            return {"connected": True}
        return {"connected": False, "error": f"HTTP {res.status_code}"}
    except Exception as e:
        return {"connected": False, "error": str(e)}


@app.post("/api/setup/test-email")
async def test_email(request: Request):
    import imaplib
    data = await request.json()
    server = data.get("server", "").strip()
    port = int(data.get("port", 993))
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not server or not username:
        return {"connected": False, "error": "Server and username required"}

    def _test():
        mail = imaplib.IMAP4_SSL(server, port)
        mail.login(username, password)
        mail.logout()

    try:
        await asyncio.to_thread(_test)
        return {"connected": True}
    except Exception as e:
        return {"connected": False, "error": str(e)}


@app.get("/memories")
async def serve_memories():
    if not is_configured():
        return RedirectResponse("/setup")
    return FileResponse(frontend_path / "memories.html")


@app.get("/settings")
async def serve_settings():
    if not is_configured():
        return RedirectResponse("/setup")
    return FileResponse(frontend_path / "settings.html")


@app.get("/api/voice/status")
async def voice_status_fallback():
    return {"stt": False, "tts": False}


@app.post("/api/upload/document")
async def upload_document(file: UploadFile):
    import io
    name = file.filename or "document"
    content = await file.read()
    text = ""
    if name.lower().endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(content))
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n\n".join(p for p in pages if p.strip())
        except Exception as e:
            return JSONResponse({"error": f"PDF read failed: {e}"}, status_code=400)
    else:
        try:
            text = content.decode("utf-8", errors="replace")
        except Exception:
            return JSONResponse({"error": "Could not decode file as text"}, status_code=400)
    return {"name": name, "text": text, "length": len(text)}
