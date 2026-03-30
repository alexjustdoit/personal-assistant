from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from backend.routers import chat, voice
from backend.services.llm import llm_router

app = FastAPI(title="Home Assistant")

app.include_router(chat.router)
app.include_router(voice.router)

frontend_path = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=frontend_path), name="static")


@app.get("/")
async def serve_ui():
    return FileResponse(frontend_path / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/history/{session_id}")
async def get_history(session_id: str):
    from backend.services.memory import memory_service
    return {"messages": memory_service.get_history(session_id)}


@app.get("/api/providers")
async def get_providers():
    return {
        "providers": llm_router.available_providers(),
        "default": llm_router.provider,
    }
