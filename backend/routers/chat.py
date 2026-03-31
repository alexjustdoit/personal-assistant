import asyncio
import json
import re
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.services.llm import llm_router
from backend.services.memory import memory_service

router = APIRouter()

REMINDER_TRIGGER = re.compile(r"(?i)\b(remind me|set a reminder|reminder)\b")

_SEARCH_SYSTEM = "You are a search router. Reply with JSON only, no explanation."
_SEARCH_PROMPT = (
    "Does answering this message well require current or real-time information "
    "(e.g. breaking news, live prices, recent events, today's results, latest releases)?\n"
    'Message: "{msg}"\n'
    'JSON: {{"search": true, "query": "concise search query"}} or {{"search": false}}'
)

_MEMORY_SYSTEM = "You extract memorable personal facts. Reply with JSON only."
_MEMORY_PROMPT = (
    'User message: "{msg}"\n\n'
    "Extract facts worth remembering about this person across future conversations: "
    "preferences, relationships, habits, goals, health, job, hobbies, ongoing projects. "
    "Skip trivial or purely conversational content.\n"
    'JSON: {{"facts": ["concise fact", ...]}} or {{"facts": []}}'
)


async def extract_reminder(text: str) -> dict | None:
    """Use LLM to extract task and time from a potential reminder message."""
    response = await llm_router.complete([
        {
            "role": "system",
            "content": "Extract reminder details from the user message. Respond with JSON only, no other text.",
        },
        {
            "role": "user",
            "content": (
                f'Message: "{text}"\n\n'
                'Return JSON: {"task": "the reminder task", "time_str": "natural language time or null"}\n'
                'If not a reminder, return: {"task": null}'
            ),
        },
    ])
    json_match = re.search(r"\{.*\}", response, re.DOTALL)
    if not json_match:
        return None
    try:
        data = json.loads(json_match.group())
        return data if data.get("task") else None
    except (json.JSONDecodeError, KeyError):
        return None


def parse_due_time(time_str: str | None) -> str | None:
    if not time_str:
        return None
    try:
        import dateparser
        from datetime import timezone
        dt = dateparser.parse(time_str, settings={"PREFER_DATES_FROM": "future", "RETURN_AS_TIMEZONE_AWARE": True})
        if dt:
            return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        pass
    return None


async def _detect_search(message: str) -> tuple[bool, str | None]:
    """Quick LLM classify: does this message need a web search?"""
    try:
        response = await llm_router.complete([
            {"role": "system", "content": _SEARCH_SYSTEM},
            {"role": "user", "content": _SEARCH_PROMPT.format(msg=message)},
        ])
        m = re.search(r"\{.*?\}", response, re.DOTALL)
        if m:
            data = json.loads(m.group())
            if data.get("search"):
                return True, data.get("query") or message
    except Exception:
        pass
    return False, None


async def _auto_extract_memories(message: str):
    """Background task: extract and save facts from any user message."""
    try:
        response = await llm_router.complete([
            {"role": "system", "content": _MEMORY_SYSTEM},
            {"role": "user", "content": _MEMORY_PROMPT.format(msg=message)},
        ])
        m = re.search(r"\{.*?\}", response, re.DOTALL)
        if m:
            data = json.loads(m.group())
            for fact in data.get("facts", []):
                if fact and len(fact.strip()) > 10:
                    memory_service.save_memory(fact.strip())
    except Exception:
        pass


@router.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket):
    await websocket.accept()

    session_id = websocket.query_params.get("session_id", "default")
    history = memory_service.get_history(session_id)

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            user_message = payload.get("content", "").strip()

            if not user_message:
                continue

            provider_override = payload.get("provider") or None

            # Detect and save explicit memory phrases
            memory_text = memory_service.extract_memory(user_message)
            if memory_text:
                memory_service.save_memory(memory_text)
            else:
                # Auto-extract implicit facts in background (fire-and-forget)
                asyncio.create_task(_auto_extract_memories(user_message))

            # Detect and save reminders
            if REMINDER_TRIGGER.search(user_message):
                reminder = await extract_reminder(user_message)
                if reminder:
                    due_time = parse_due_time(reminder.get("time_str"))
                    memory_service.save_reminder(session_id, reminder["task"], due_time)

            # Retrieve relevant memories + all pending reminders (global, not session-scoped)
            relevant_memories = memory_service.search_memories(user_message)
            pending_reminders = memory_service.get_pending_reminders()
            system_prompt = memory_service.build_system_prompt(relevant_memories, pending_reminders)

            # Web search if configured and needed
            from backend.services.search import search_enabled, web_search
            if search_enabled():
                needs_search, query = await _detect_search(user_message)
                if needs_search and query:
                    await websocket.send_text(json.dumps({"type": "searching", "query": query}))
                    results = await web_search(query)
                    if results:
                        search_block = f'\n\nWeb search results for "{query}":\n'
                        for r in results[:5]:
                            if r["content"]:
                                search_block += f'• {r["title"]}: {r["content"]}\n'
                        system_prompt += search_block

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
