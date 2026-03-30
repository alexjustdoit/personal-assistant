import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.services.llm import llm_router

router = APIRouter()

SYSTEM_PROMPT = """You are a helpful personal home assistant. You are concise, friendly, and direct.
You remember context within the conversation. When you don't know something, say so."""

# In-memory conversation history per connection
# Phase 3 will replace this with ChromaDB persistent memory
sessions: dict[str, list[dict]] = {}


@router.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket):
    await websocket.accept()
    session_id = id(websocket)
    sessions[session_id] = []

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            user_message = payload.get("content", "").strip()

            if not user_message:
                continue

            provider_override = payload.get("provider") or None
            sessions[session_id].append({"role": "user", "content": user_message})

            messages = [{"role": "system", "content": SYSTEM_PROMPT}] + sessions[session_id]

            full_response = ""
            try:
                async for token in llm_router.stream(messages, provider_override=provider_override):
                    full_response += token
                    await websocket.send_text(json.dumps({"type": "token", "content": token}))

                sessions[session_id].append({"role": "assistant", "content": full_response})
                await websocket.send_text(json.dumps({"type": "done"}))

            except Exception as e:
                await websocket.send_text(json.dumps({"type": "error", "content": str(e)}))

    except WebSocketDisconnect:
        sessions.pop(session_id, None)
