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

_TODOIST_SYSTEM = "You detect task management intents. Reply with JSON only."
_TODOIST_PROMPT = (
    "Does this message want to add, list, or complete a task in a to-do list?\n"
    'Message: "{msg}"\n'
    'JSON: {{"action": "add", "task": "task text", "due": "due string or null"}} '
    'or {{"action": "list"}} '
    'or {{"action": "complete", "task_name": "task name"}} '
    'or {{"action": null}}'
)

_GOVEE_SYSTEM = "You detect smart home / light control intents. Reply with JSON only."
_GOVEE_PROMPT = (
    "Does this message want to control a smart home device (lights, lamp, etc.)?\n"
    "Available devices: {devices}\n"
    'Message: "{msg}"\n'
    'JSON: {{"action": "on"|"off"|"brightness"|"color"|"color_temp", '
    '"device": "device name or all", '
    '"brightness": 0-100 or null, '
    '"color": "color name or r,g,b or null", '
    '"color_temp": kelvin or null}} '
    'or {{"action": null}}'
)


async def extract_reminder(text: str) -> dict | None:
    response = await llm_router.complete([
        {"role": "system", "content": "Extract reminder details from the user message. Respond with JSON only, no other text."},
        {"role": "user", "content": (
            f'Message: "{text}"\n\n'
            'Return JSON: {"task": "the reminder task", "time_str": "natural language time or null"}\n'
            'If not a reminder, return: {"task": null}'
        )},
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


async def _detect_todoist(message: str) -> dict | None:
    try:
        response = await llm_router.complete([
            {"role": "system", "content": _TODOIST_SYSTEM},
            {"role": "user", "content": _TODOIST_PROMPT.format(msg=message)},
        ])
        m = re.search(r"\{.*?\}", response, re.DOTALL)
        if m:
            data = json.loads(m.group())
            if data.get("action"):
                return data
    except Exception:
        pass
    return None


async def _detect_govee(message: str) -> dict | None:
    from backend.services.govee import get_devices
    devices = await get_devices()
    device_names = ", ".join(d.get("deviceName", "?") for d in devices) or "none"
    try:
        response = await llm_router.complete([
            {"role": "system", "content": _GOVEE_SYSTEM},
            {"role": "user", "content": _GOVEE_PROMPT.format(msg=message, devices=device_names)},
        ])
        m = re.search(r"\{.*?\}", response, re.DOTALL)
        if m:
            data = json.loads(m.group())
            if data.get("action"):
                return data
    except Exception:
        pass
    return None


async def _auto_extract_memories(message: str):
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
            image_data = payload.get("image")  # "data:<media_type>;base64,<data>" or None

            if not user_message and not image_data:
                continue

            provider_override = payload.get("provider") or None

            # --- Memory ---
            if user_message:
                memory_text = memory_service.extract_memory(user_message)
                if memory_text:
                    memory_service.save_memory(memory_text)
                else:
                    asyncio.create_task(_auto_extract_memories(user_message))

            # --- Reminders ---
            if user_message and REMINDER_TRIGGER.search(user_message):
                reminder = await extract_reminder(user_message)
                if reminder:
                    due_time = parse_due_time(reminder.get("time_str"))
                    memory_service.save_reminder(session_id, reminder["task"], due_time)

            # --- System prompt ---
            relevant_memories = memory_service.search_memories(user_message) if user_message else []
            pending_reminders = memory_service.get_pending_reminders()
            system_prompt = memory_service.build_system_prompt(relevant_memories, pending_reminders, query=user_message)

            # --- Parallel: search + todoist detect ---
            from backend.services.search import search_enabled, web_search
            from backend.services.todoist import todoist_enabled, get_tasks, add_task, complete_task, find_task_by_name
            from backend.services.govee import govee_enabled, execute_govee_intent

            detect_tasks = {}
            if user_message and search_enabled():
                detect_tasks["search"] = asyncio.create_task(_detect_search(user_message))
            if user_message and todoist_enabled():
                detect_tasks["todoist"] = asyncio.create_task(_detect_todoist(user_message))
            if user_message and govee_enabled():
                detect_tasks["govee"] = asyncio.create_task(_detect_govee(user_message))

            search_result = None
            todoist_result = None
            govee_result = None
            if detect_tasks:
                await asyncio.gather(*detect_tasks.values(), return_exceptions=True)
                if "search" in detect_tasks:
                    search_result = detect_tasks["search"].result() if not detect_tasks["search"].exception() else (False, None)
                if "todoist" in detect_tasks:
                    todoist_result = detect_tasks["todoist"].result() if not detect_tasks["todoist"].exception() else None
                if "govee" in detect_tasks:
                    govee_result = detect_tasks["govee"].result() if not detect_tasks["govee"].exception() else None

            # --- Web search ---
            if search_result and search_result[0]:
                _, query = search_result
                await websocket.send_text(json.dumps({"type": "searching", "query": query}))
                results = await web_search(query)
                if results:
                    block = f'\n\nWeb search results for "{query}":\n'
                    for r in results[:5]:
                        if r["content"]:
                            block += f'• {r["title"]}: {r["content"]}\n'
                    system_prompt += block

            # --- Todoist actions ---
            if todoist_result:
                action = todoist_result.get("action")
                if action == "add":
                    task_content = todoist_result.get("task", user_message)
                    due = todoist_result.get("due")
                    created = await add_task(task_content, due)
                    if created:
                        system_prompt += f'\n\n[Todoist] Added task: "{task_content}"' + (f', due: {due}' if due else '') + '. Confirm to the user.'
                    else:
                        system_prompt += '\n\n[Todoist] Failed to add the task. Apologize briefly.'
                elif action == "list":
                    tasks = await get_tasks("today | overdue")
                    if tasks:
                        lines = "\n".join(f'- {t["content"]}' + (f' (due: {t["due"]["string"]})' if t.get("due") else '') for t in tasks)
                        system_prompt += f'\n\n[Todoist] Current tasks:\n{lines}\nSummarize these for the user.'
                    else:
                        system_prompt += '\n\n[Todoist] No tasks due today or overdue. Tell the user their list is clear.'
                elif action == "complete":
                    task_name = todoist_result.get("task_name", "")
                    task = await find_task_by_name(task_name)
                    if task:
                        ok = await complete_task(task["id"])
                        if ok:
                            system_prompt += f'\n\n[Todoist] Completed task: "{task["content"]}". Confirm to the user.'
                        else:
                            system_prompt += '\n\n[Todoist] Failed to complete the task. Apologize briefly.'
                    else:
                        system_prompt += f'\n\n[Todoist] Could not find a task matching "{task_name}". Tell the user.'

            # --- Govee smart home ---
            if govee_result:
                result_text = await execute_govee_intent(govee_result)
                system_prompt += f"\n\n{result_text}"

            # --- Save & build messages ---
            if user_message:
                history.append({"role": "user", "content": user_message})
                memory_service.save_message(session_id, "user", user_message)

            messages = [{"role": "system", "content": system_prompt}] + history

            # --- Stream response ---
            full_response = ""
            try:
                if image_data:
                    # Parse data URL
                    if "," in image_data:
                        header, b64 = image_data.split(",", 1)
                        media_type = header.split(";")[0].split(":")[1]
                    else:
                        b64, media_type = image_data, "image/jpeg"
                    vision_provider = llm_router.best_vision_provider(provider_override)
                    async for token in llm_router.stream_vision(messages, b64, media_type, vision_provider):
                        full_response += token
                        await websocket.send_text(json.dumps({"type": "token", "content": token}))
                else:
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
