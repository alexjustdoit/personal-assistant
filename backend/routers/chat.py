import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.services.llm import llm_router
from backend.services.memory import memory_service

router = APIRouter()


@router.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket):
    await websocket.accept()

    # Session ID comes from the frontend (stored in localStorage)
    session_id = websocket.query_params.get("session_id", "default")

    # Load persisted history for this session
    history = memory_service.get_history(session_id)

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            user_message = payload.get("content", "").strip()

            if not user_message:
                continue

            provider_override = payload.get("provider") or None

            # Check if user is asking to remember something
            memory_text = memory_service.extract_memory(user_message)
            if memory_text:
                memory_service.save_memory(memory_text)

            # Retrieve relevant memories to inform the response
            relevant_memories = memory_service.search_memories(user_message)
            system_prompt = memory_service.build_system_prompt(relevant_memories)

            history.append({"role": "user", "content": user_message})
            memory_service.save_message(session_id, "user", user_message)

            messages = [{"role": "system", "content": system_prompt}] + history

            full_response = ""
            try:
                async for token in llm_router.stream(messages, provider_override=provider_override):
                    full_response += token
                    await websocket.send_text(json.dumps({"type": "token", "content": token}))

                history.append({"role": "assistant", "content": full_response})
                memory_service.save_message(session_id, "assistant", full_response)
                await websocket.send_text(json.dumps({"type": "done"}))

            except Exception as e:
                await websocket.send_text(json.dumps({"type": "error", "content": str(e)}))

    except WebSocketDisconnect:
        pass
