import asyncio
import json
import re
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.services.llm import llm_router
from backend.services.memory import memory_service

router = APIRouter()

REMINDER_TRIGGER = re.compile(r"(?i)\b(remind me|set a reminder|reminder)\b")

# Keyword hints — skip LLM detection entirely if message has no relevant terms
_SEARCH_HINT = re.compile(
    r"\b(news|today|latest|current|recent|live|price|stock|weather|score|result|update|breaking|trending|now|who won|what happened)\b",
    re.I,
)
_TODOIST_HINT = re.compile(
    r"\b(task|tasks|todo|to-do|add|remind|complete|done|finish|list my|show my|schedule|due)\b",
    re.I,
)
_GOVEE_HINT = re.compile(
    r"\b(light|lights|lamp|bright|dim|turn on|turn off|smart home|color|colour|kelvin)\b",
    re.I,
)
_IGNORE_SITE_HINT = re.compile(
    r"\b(ignore|stop (logging|tracking|recording)|don'?t (log|track|record))\b",
    re.I,
)
_EMAIL_HINT = re.compile(
    r"\b(email|emails|inbox|mail|messages?)\b",
    re.I,
)
_FOLLOWUP_HINT = re.compile(
    r"\b(i'?ll\b|i will\b|i need to\b|i should\b|i'?m going to\b|i have to\b|i plan to\b|i'?ve been meaning to\b|don'?t let me forget)\b",
    re.I,
)

_SESSION_HINT = re.compile(
    r"\b(session|last week|this week|what did (i|we) (work on|do|build|implement|fix|add)|"
    r"what (have i|was i|were we) (working on|doing)|recent work|"
    r"(tam copilot|discovery assistant|personal assistant) (progress|update|changes|status)|"
    r"what did (claude|you) (do|help)|recap|summary of (work|session))\b",
    re.I,
)

_CALENDAR_HINT = re.compile(
    r"\b(schedule|book|create an? event|add (?:an? )?(?:event|meeting|appointment)|put on (?:my )?calendar|block (?:off )?(?:time|my)|meeting|appointment)\b",
    re.I,
)

_CALENDAR_SYSTEM = "You detect calendar event creation intents. Reply with JSON only."
_CALENDAR_PROMPT = (
    "Does this message want to schedule or create a calendar event?\n"
    'Message: "{msg}"\n'
    'Current date/time: {now}\n'
    'JSON: {{"action": "create", "title": "event title", "start": "natural language date and time", "duration_minutes": 60}} '
    'or {{"action": null}}'
)

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
    'JSON: {{"action": "add", "task": "task text", "due": "due string or null", "project": "project name or null"}} '
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

_IGNORE_SITE_SYSTEM = "You detect requests to ignore a website from activity logging. Reply with JSON only."
_IGNORE_SITE_PROMPT = (
    "Does this message ask to stop logging, tracking, or recording a specific website or domain?\n"
    'Message: "{msg}"\n'
    'JSON: {{"domain": "domain.com"}} or {{"domain": null}}'
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


def _parse_datetime(time_str: str | None) -> "datetime | None":
    """Parse a natural language time string into a local naive datetime."""
    if not time_str:
        return None
    try:
        import dateparser
        dt = dateparser.parse(time_str, settings={"PREFER_DATES_FROM": "future", "RETURN_AS_TIMEZONE_AWARE": False})
        return dt
    except Exception:
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
        response = await llm_router.complete_detect([
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
        response = await llm_router.complete_detect([
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
        response = await llm_router.complete_detect([
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


async def _detect_ignore_site(message: str) -> str | None:
    """Returns a domain string if the user wants to ignore it, else None."""
    try:
        response = await llm_router.complete_detect([
            {"role": "system", "content": _IGNORE_SITE_SYSTEM},
            {"role": "user", "content": _IGNORE_SITE_PROMPT.format(msg=message)},
        ])
        m = re.search(r"\{.*?\}", response, re.DOTALL)
        if m:
            data = json.loads(m.group())
            return data.get("domain") or None
    except Exception:
        pass
    return None


async def _detect_calendar(message: str) -> dict | None:
    from datetime import datetime as _dt
    now = _dt.now().strftime("%A, %B %d, %Y %I:%M %p")
    try:
        response = await llm_router.complete_detect([
            {"role": "system", "content": _CALENDAR_SYSTEM},
            {"role": "user", "content": _CALENDAR_PROMPT.format(msg=message, now=now)},
        ])
        m = re.search(r"\{.*?\}", response, re.DOTALL)
        if m:
            data = json.loads(m.group())
            if data.get("action"):
                return data
    except Exception:
        pass
    return None


async def _auto_title_and_send(session_id: str, user_message: str, response_preview: str, websocket):
    """Generate a short chat title after the first exchange and push it to the client."""
    try:
        already_named = await asyncio.to_thread(memory_service.has_custom_name, session_id)
        if already_named:
            return
        response = await llm_router.complete_detect([
            {"role": "system", "content": "Write a short chat title. Reply with only the title — no quotes, no period."},
            {"role": "user", "content": (
                f"User: {user_message[:200]}\nAssistant: {response_preview[:200]}\n\n"
                "Title (3-6 words):"
            )},
        ])
        title = response.strip().strip('"\'').strip('.')[:80]
        if title:
            await asyncio.to_thread(memory_service.rename_chat, session_id, title)
            await websocket.send_text(json.dumps({"type": "title", "title": title}))
    except Exception:
        pass


async def _check_for_followups(user_message: str):
    """If the user mentioned a future commitment not flagged as a reminder, save it and notify."""
    try:
        response = await llm_router.complete_detect([
            {"role": "system", "content": "Extract future task commitments. Reply with JSON only."},
            {"role": "user", "content": (
                f'User message: "{user_message}"\n\n'
                "If the user mentioned a specific concrete task they plan to do in the future "
                "(not a question, not already done, not vague), extract it as a short phrase (under 10 words). "
                'JSON: {"task": "short task"} or {"task": null}'
            )},
        ])
        m = re.search(r"\{.*?\}", response, re.DOTALL)
        if m:
            data = json.loads(m.group())
            task = (data.get("task") or "").strip()
            if task and len(task) > 5:
                await asyncio.to_thread(memory_service.create_reminder, task)
                from backend.services.notification_queue import push as push_browser
                push_browser("Reminder saved", task)
    except Exception:
        pass


async def _summarize_if_needed(session_id: str, history: list):
    """When history hits 40 messages, compress the oldest 20 into a summary row."""
    if len(history) < 40:
        return
    try:
        msgs = await asyncio.to_thread(memory_service.get_messages_to_summarize, session_id, 20)
        if len(msgs) < 10:
            return
        block = "\n".join(f"{m['role'].upper()}: {m['content'][:300]}" for m in msgs)
        summary = await llm_router.complete([
            {"role": "system", "content": "Summarize this conversation excerpt concisely in 3-5 sentences, preserving key facts, decisions, and context. Reply with only the summary."},
            {"role": "user", "content": block},
        ])
        if summary.strip():
            ids = [m["id"] for m in msgs]
            await asyncio.to_thread(memory_service.compress_messages, session_id, ids, summary.strip())
            del history[:20]
    except Exception:
        pass


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
                    await asyncio.to_thread(memory_service.save_memory, fact.strip())
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
            document = payload.get("document")  # {name, text} or None
            is_regenerate = payload.get("regenerate", False)

            if not user_message and not image_data:
                continue

            provider_override = payload.get("provider") or None

            # Regenerate: drop the last assistant turn from in-memory history
            if is_regenerate and history and history[-1]["role"] == "assistant":
                history.pop()

            # --- Memory ---
            if user_message:
                memory_text = memory_service.extract_memory(user_message)
                if memory_text:
                    asyncio.create_task(asyncio.to_thread(memory_service.save_memory, memory_text))
                else:
                    asyncio.create_task(_auto_extract_memories(user_message))

            # --- Reminders ---
            _explicit_reminder = bool(user_message and REMINDER_TRIGGER.search(user_message))
            if _explicit_reminder:
                reminder = await extract_reminder(user_message)
                if reminder:
                    due_time = parse_due_time(reminder.get("time_str"))
                    await asyncio.to_thread(memory_service.save_reminder, session_id, reminder["task"], due_time)

            # --- System prompt ---
            relevant_memories = await asyncio.to_thread(memory_service.search_memories, user_message) if user_message else []
            pending_reminders = await asyncio.to_thread(memory_service.get_pending_reminders)
            conv_summary = await asyncio.to_thread(memory_service.get_conversation_summary, session_id)
            system_prompt = memory_service.build_system_prompt(relevant_memories, pending_reminders, query=user_message, conv_summary=conv_summary)

            # --- Parallel: search + todoist detect ---
            from backend.services.search import search_enabled, web_search
            from backend.services.todoist import todoist_enabled, get_tasks, add_task, complete_task, find_task_by_name, get_projects
            from backend.services.govee import govee_enabled, execute_govee_intent

            from backend.services.activity_tracker import add_ignored_domain
            from backend.services.email_service import email_enabled, fetch_emails

            detect_tasks = {}
            if user_message and search_enabled() and _SEARCH_HINT.search(user_message):
                detect_tasks["search"] = asyncio.create_task(_detect_search(user_message))
            if user_message and todoist_enabled() and _TODOIST_HINT.search(user_message):
                detect_tasks["todoist"] = asyncio.create_task(_detect_todoist(user_message))
            if user_message and govee_enabled() and _GOVEE_HINT.search(user_message):
                detect_tasks["govee"] = asyncio.create_task(_detect_govee(user_message))
            from backend.services.calendar_service import calendar_service
            if user_message and calendar_service.caldav_enabled() and _CALENDAR_HINT.search(user_message):
                detect_tasks["calendar"] = asyncio.create_task(_detect_calendar(user_message))
            if user_message and _IGNORE_SITE_HINT.search(user_message):
                detect_tasks["ignore_site"] = asyncio.create_task(_detect_ignore_site(user_message))
            if user_message and email_enabled() and _EMAIL_HINT.search(user_message):
                detect_tasks["email"] = asyncio.create_task(fetch_emails())
            from backend.services.sessions_reader import is_session_query, search_sessions
            if user_message and is_session_query(user_message):
                detect_tasks["sessions"] = asyncio.create_task(
                    asyncio.to_thread(search_sessions, user_message)
                )

            search_result = None
            todoist_result = None
            govee_result = None
            ignore_site_result = None
            email_result = None
            sessions_result = []
            calendar_result = None
            if detect_tasks:
                await asyncio.gather(*detect_tasks.values(), return_exceptions=True)
                if "search" in detect_tasks:
                    search_result = detect_tasks["search"].result() if not detect_tasks["search"].exception() else (False, None)
                if "todoist" in detect_tasks:
                    todoist_result = detect_tasks["todoist"].result() if not detect_tasks["todoist"].exception() else None
                if "govee" in detect_tasks:
                    govee_result = detect_tasks["govee"].result() if not detect_tasks["govee"].exception() else None
                if "ignore_site" in detect_tasks:
                    ignore_site_result = detect_tasks["ignore_site"].result() if not detect_tasks["ignore_site"].exception() else None
                if "email" in detect_tasks:
                    email_result = detect_tasks["email"].result() if not detect_tasks["email"].exception() else None
                if "sessions" in detect_tasks:
                    sessions_result = detect_tasks["sessions"].result() if not detect_tasks["sessions"].exception() else []
                if "calendar" in detect_tasks:
                    calendar_result = detect_tasks["calendar"].result() if not detect_tasks["calendar"].exception() else None

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
                    project_name = todoist_result.get("project")
                    project_id = None
                    if project_name:
                        projects = await get_projects()
                        match = next((p for p in projects if project_name.lower() in p.get("name", "").lower()), None)
                        if match:
                            project_id = match["id"]
                    created = await add_task(task_content, due, project_id)
                    if created:
                        proj_label = f' in project "{match["name"]}"' if project_id and match else ''
                        system_prompt += f'\n\n[Todoist] Added task: "{task_content}"{proj_label}' + (f', due: {due}' if due else '') + '. Confirm to the user.'
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

            # --- Ignore site ---
            if ignore_site_result:
                added = await asyncio.to_thread(add_ignored_domain, ignore_site_result)
                if added:
                    system_prompt += f'\n\n[Activity] Added "{ignore_site_result}" to ignored domains and removed it from existing log files. It will no longer appear in any activity logs. Confirm to the user.'
                else:
                    system_prompt += f'\n\n[Activity] "{ignore_site_result}" is already in the ignored domains list. Tell the user it was already ignored.'

            # --- Email ---
            if email_result is not None:
                if email_result:
                    lines = "\n".join(
                        f"- [{e['account']}] From: {e['from']} | Subject: {e['subject']}" +
                        (f" | {e['date']}" if e.get("date") else "") +
                        (f"\n  {e['body'][:200]}" if e.get("body") else "")
                        for e in email_result[:20]
                    )
                    system_prompt += f"\n\nRecent emails ({len(email_result)} total):\n{lines}"
                else:
                    system_prompt += "\n\n[Email] No recent emails found."

            # --- Work sessions ---
            if sessions_result:
                lines = "\n\n---\n\n".join(
                    f"[{s['source']}]\n{s['excerpt']}" for s in sessions_result
                )
                system_prompt += f"\n\nContext from past work sessions:\n{lines}"

            # --- Calendar create ---
            if calendar_result and calendar_result.get("action") == "create":
                from datetime import timedelta as _td
                title = calendar_result.get("title", "Event")
                start_dt = _parse_datetime(calendar_result.get("start", ""))
                duration = int(calendar_result.get("duration_minutes") or 60)
                if start_dt:
                    end_dt = start_dt + _td(minutes=duration)
                    ok = await calendar_service.create_event(title, start_dt, end_dt)
                    if ok:
                        system_prompt += f'\n\n[Calendar] Created event: "{title}" on {start_dt.strftime("%A, %B %d at %I:%M %p")}. Confirm to the user.'
                    else:
                        system_prompt += '\n\n[Calendar] Failed to create the event — check CalDAV settings. Apologize briefly.'
                else:
                    system_prompt += f'\n\n[Calendar] Could not parse the event time. Ask the user to clarify when they want to schedule "{title}".'

            # --- Document context ---
            if document and document.get("text"):
                doc_text = document["text"]
                truncated = len(doc_text) > 12000
                system_prompt += f'\n\nThe user attached a document: "{document.get("name", "document")}"\n\n{doc_text[:12000]}'
                if truncated:
                    system_prompt += "\n\n[Note: document was truncated to fit context window]"

            # --- Save & build messages ---
            if user_message and not is_regenerate:
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

                # Auto-title on first exchange
                if len(history) == 2 and user_message:
                    asyncio.create_task(_auto_title_and_send(session_id, user_message, full_response, websocket))

                # Compress history when it gets long
                asyncio.create_task(_summarize_if_needed(session_id, history))

                # Proactive follow-up: save implied commitments as reminders
                if user_message and not _explicit_reminder and _FOLLOWUP_HINT.search(user_message):
                    asyncio.create_task(_check_for_followups(user_message))

            except Exception as e:
                await websocket.send_text(json.dumps({"type": "error", "content": str(e)}))

    except WebSocketDisconnect:
        pass
