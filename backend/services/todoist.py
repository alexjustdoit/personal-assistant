import httpx
from backend.config import config

_BASE = "https://api.todoist.com/rest/v2"


def _token() -> str:
    return config.get("todoist", {}).get("api_token", "")


def todoist_enabled() -> bool:
    return bool(_token())


def _headers() -> dict:
    return {"Authorization": f"Bearer {_token()}"}


async def get_tasks(filter_str: str = "today | overdue") -> list[dict]:
    """Return tasks matching the given Todoist filter query."""
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"{_BASE}/tasks",
                headers=_headers(),
                params={"filter": filter_str},
                timeout=10,
            )
            res.raise_for_status()
            return res.json()
    except Exception:
        return []


async def get_projects() -> list[dict]:
    """Return all user projects."""
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(f"{_BASE}/projects", headers=_headers(), timeout=10)
            res.raise_for_status()
            return res.json()
    except Exception:
        return []


async def add_task(content: str, due_string: str | None = None, project_id: str | None = None) -> dict | None:
    """Create a new task. Returns the created task dict or None on failure."""
    payload: dict = {"content": content}
    if due_string:
        payload["due_string"] = due_string
    if project_id:
        payload["project_id"] = project_id
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{_BASE}/tasks",
                headers=_headers(),
                json=payload,
                timeout=10,
            )
            res.raise_for_status()
            return res.json()
    except Exception:
        return None


async def complete_task(task_id: str) -> bool:
    """Mark a task as complete. Returns True on success."""
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{_BASE}/tasks/{task_id}/close",
                headers=_headers(),
                timeout=10,
            )
            return res.status_code == 204
    except Exception:
        return False


async def find_task_by_name(name: str) -> dict | None:
    """Find an active task whose content contains the given name (case-insensitive)."""
    tasks = await get_tasks("today | overdue | !assigned to: others")
    name_lower = name.lower()
    for task in tasks:
        if name_lower in task.get("content", "").lower():
            return task
    # Broader search if no match
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(f"{_BASE}/tasks", headers=_headers(), timeout=10)
            res.raise_for_status()
            all_tasks = res.json()
        for task in all_tasks:
            if name_lower in task.get("content", "").lower():
                return task
    except Exception:
        pass
    return None
