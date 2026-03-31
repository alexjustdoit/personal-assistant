import asyncio
import os
import sys
import yaml
import httpx
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from backend.config import is_configured, CONFIG_PATH
from backend.routers import chat, voice

app = FastAPI(title="Home Assistant")

frontend_path = Path(__file__).parent.parent / "frontend"


@app.on_event("startup")
async def startup():
    if is_configured():
        from backend.services.scheduler import scheduler_service
        scheduler_service.start()


@app.on_event("shutdown")
async def shutdown():
    if is_configured():
        try:
            from backend.services.scheduler import scheduler_service
            scheduler_service.stop()
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


@app.get("/api/chats")
async def get_chats():
    from backend.services.memory import memory_service
    return {"chats": memory_service.get_chats()}


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
    from backend.services.briefing import generate_on_demand_briefing
    return await generate_on_demand_briefing(period, force=force, provider=provider)


@app.get("/api/calendar/events")
async def get_calendar_events():
    from backend.services.calendar_service import calendar_service
    events = await calendar_service.get_events()
    return {"events": events}


@app.get("/api/providers")
async def get_providers():
    from backend.services.llm import llm_router
    return {
        "providers": llm_router.available_providers(),
        "default": llm_router.provider,
    }


@app.get("/api/voice/status")
async def voice_status_fallback():
    return {"stt": False, "tts": False}
