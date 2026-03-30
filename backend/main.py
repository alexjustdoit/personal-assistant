from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from backend.routers import chat

app = FastAPI(title="Home Assistant")

app.include_router(chat.router)

frontend_path = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=frontend_path), name="static")


@app.get("/")
async def serve_ui():
    return FileResponse(frontend_path / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}
