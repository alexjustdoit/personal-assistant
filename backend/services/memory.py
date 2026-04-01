import re
import sqlite3
import asyncio
import uuid
from pathlib import Path
from datetime import datetime, timedelta

DATA_DIR = Path(__file__).parent.parent.parent / "data"
DB_PATH = DATA_DIR / "conversations.db"
CHROMA_PATH = str(DATA_DIR / "chroma")

MEMORY_PATTERNS = [
    r"(?i)(?:please )?remember that (.+)",
    r"(?i)(?:please )?remember (.+)",
    r"(?i)(?:please )?note that (.+)",
    r"(?i)don'?t forget (?:that )?(.+)",
    r"(?i)keep in mind (?:that )?(.+)",
]

SYSTEM_BASE = """You are a personal AI assistant running on the user's own hardware with a custom backend. Be extremely concise and direct.

Rules:
- Reply in 1-3 sentences for simple questions. Never pad, explain, or repeat yourself.
- Only use bullet points or lists when the user explicitly asks for them or when listing 3+ distinct items.
- Do not start responses with phrases like "Sure!", "Of course!", "Great question!", or "Certainly!".
- Do not summarize what you just said at the end of a response.
- If you don't know something, say so in one sentence.
- If the user asks you to remember something, confirm in one short sentence.
- Never say you are limited to this conversation, cannot access external services, or cannot browse the internet. The backend handles those things for you — do not disclaim capabilities you actually have.

Capabilities the backend provides you:
- Personal memory: facts about the user are retrieved from a local ChromaDB vector database and injected above when relevant.
- Personal notes: markdown and text files from configured local and iCloud folders are watched and indexed — their contents appear above when relevant to the conversation.
- Reminders: you can set reminders (e.g. "remind me to...") and pending ones appear above.
- Web search: when you need current information, a web search is run automatically and results are injected above."""


class MemoryService:
    def __init__(self):
        DATA_DIR.mkdir(exist_ok=True)
        self._init_db()
        self._chroma_collection = None

    # --- SQLite: conversation history ---

    def _init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    due_time TEXT,
                    completed INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS briefings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    generated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_names (
                    session_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    archived INTEGER DEFAULT 0
                )
            """)
            # Migrate: add archived column if it doesn't exist yet
            try:
                conn.execute("ALTER TABLE chat_names ADD COLUMN archived INTEGER DEFAULT 0")
            except Exception:
                pass
            conn.commit()

    def _run_sync(self, fn, *args):
        return asyncio.get_event_loop().run_in_executor(None, fn, *args)

    def save_message(self, session_id: str, role: str, content: str):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, role, content, datetime.utcnow().isoformat()),
            )
            conn.commit()

    def get_history(self, session_id: str, limit: int = 40) -> list[dict]:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute(
                "SELECT role, content, timestamp FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [{"role": r, "content": c, "timestamp": t} for r, c, t in reversed(rows)]

    # --- ChromaDB: personal memory ---

    def _get_collection(self):
        if self._chroma_collection is None:
            import chromadb
            client = chromadb.PersistentClient(path=CHROMA_PATH)
            self._chroma_collection = client.get_or_create_collection("personal_memory")
        return self._chroma_collection

    def save_memory(self, text: str):
        col = self._get_collection()
        col.add(
            documents=[text],
            ids=[str(uuid.uuid4())],
            metadatas=[{"timestamp": datetime.utcnow().isoformat()}],
        )

    def search_memories(self, query: str, n: int = 3) -> list[str]:
        col = self._get_collection()
        count = col.count()
        if count == 0:
            return []
        results = col.query(query_texts=[query], n_results=min(n, count))
        return results["documents"][0] if results["documents"] else []

    def delete_memory(self, text: str):
        col = self._get_collection()
        results = col.query(query_texts=[text], n_results=1)
        if results["ids"] and results["ids"][0]:
            col.delete(ids=[results["ids"][0][0]])

    def list_memories(self) -> list[dict]:
        col = self._get_collection()
        if col.count() == 0:
            return []
        result = col.get(include=["documents", "metadatas"])
        return [
            {"id": id_, "text": doc, "timestamp": (meta or {}).get("timestamp", "")}
            for id_, doc, meta in zip(result["ids"], result["documents"], result["metadatas"])
        ]

    def delete_memory_by_id(self, memory_id: str):
        col = self._get_collection()
        col.delete(ids=[memory_id])

    # --- SQLite: reminders ---

    def save_reminder(self, session_id: str, text: str, due_time: str | None = None):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO reminders (session_id, text, due_time, created_at) VALUES (?, ?, ?, ?)",
                (session_id, text, due_time, datetime.utcnow().isoformat()),
            )
            conn.commit()

    def get_pending_reminders(self, session_id: str | None = None) -> list[dict]:
        with sqlite3.connect(DB_PATH) as conn:
            if session_id:
                rows = conn.execute(
                    "SELECT id, text, due_time FROM reminders WHERE session_id = ? AND completed = 0 ORDER BY due_time",
                    (session_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, text, due_time FROM reminders WHERE completed = 0 ORDER BY due_time",
                ).fetchall()
        return [{"id": r[0], "text": r[1], "due_time": r[2]} for r in rows]

    def get_due_reminders(self) -> list[dict]:
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute(
                "SELECT id, text, due_time FROM reminders WHERE completed = 0 AND due_time IS NOT NULL AND due_time <= ?",
                (now,),
            ).fetchall()
        return [{"id": r[0], "text": r[1], "due_time": r[2]} for r in rows]

    def complete_reminder(self, reminder_id: int):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE reminders SET completed = 1 WHERE id = ?", (reminder_id,))
            conn.commit()

    # --- SQLite: briefings ---

    def save_briefing(self, content: str):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO briefings (content, generated_at) VALUES (?, ?)",
                (content, datetime.utcnow().isoformat()),
            )
            conn.commit()

    def get_recent_briefing(self, max_age_hours: int = 6) -> dict | None:
        cutoff = (datetime.utcnow() - timedelta(hours=max_age_hours)).isoformat()
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT content, generated_at FROM briefings WHERE generated_at > ? ORDER BY id DESC LIMIT 1",
                (cutoff,),
            ).fetchone()
        if row:
            return {"content": row[0], "generated_at": row[1]}
        return None

    def get_latest_briefing(self) -> dict | None:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT content, generated_at FROM briefings ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row:
            return {"content": row[0], "generated_at": row[1]}
        return None

    # --- SQLite: chat list ---

    def get_chats(self, include_archived: bool = False) -> list[dict]:
        with sqlite3.connect(DB_PATH) as conn:
            archived_filter = "" if include_archived else "AND (cn.archived IS NULL OR cn.archived = 0)"
            rows = conn.execute(f"""
                SELECT
                    m.session_id,
                    MIN(m.timestamp) AS created_at,
                    MAX(m.timestamp) AS last_active,
                    COALESCE(cn.name,
                        (SELECT content FROM messages
                         WHERE session_id = m.session_id AND role = 'user'
                         ORDER BY id LIMIT 1)
                    ) AS name,
                    COALESCE(cn.archived, 0) AS archived
                FROM messages m
                LEFT JOIN chat_names cn ON m.session_id = cn.session_id
                GROUP BY m.session_id
                {archived_filter}
                ORDER BY last_active DESC
            """).fetchall()
        return [
            {"id": r[0], "name": r[3] or "New chat", "created_at": r[1], "last_active": r[2], "archived": bool(r[4])}
            for r in rows
        ]

    def archive_chat(self, session_id: str):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO chat_names (session_id, name, archived) VALUES (?, COALESCE((SELECT name FROM chat_names WHERE session_id = ?), ''), 1) "
                "ON CONFLICT(session_id) DO UPDATE SET archived = 1",
                (session_id, session_id),
            )
            conn.commit()

    def unarchive_chat(self, session_id: str):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "UPDATE chat_names SET archived = 0 WHERE session_id = ?",
                (session_id,),
            )
            conn.commit()

    def delete_chat(self, session_id: str):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM chat_names WHERE session_id = ?", (session_id,))
            conn.commit()

    def rename_chat(self, session_id: str, name: str):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO chat_names (session_id, name) VALUES (?, ?)",
                (session_id, name.strip()[:120]),
            )
            conn.commit()

    def search_messages(self, query: str, limit: int = 20) -> list[dict]:
        like = f"%{query}%"
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute("""
                SELECT DISTINCT
                    m.session_id,
                    COALESCE(cn.name,
                        (SELECT content FROM messages
                         WHERE session_id = m.session_id AND role = 'user'
                         ORDER BY id LIMIT 1)
                    ) AS chat_name,
                    m.content,
                    m.timestamp
                FROM messages m
                LEFT JOIN chat_names cn ON m.session_id = cn.session_id
                WHERE m.content LIKE ?
                ORDER BY m.timestamp DESC
                LIMIT ?
            """, (like, limit)).fetchall()
        return [
            {
                "session_id": r[0],
                "chat_name": r[1] or "New chat",
                "snippet": r[2][:120],
                "timestamp": r[3],
            }
            for r in rows
        ]

    # --- Memory detection ---

    def extract_memory(self, text: str) -> str | None:
        for pattern in MEMORY_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip().rstrip(".")
        return None

    # --- System prompt builder ---

    def build_system_prompt(self, memories: list[str], reminders: list[dict] | None = None, query: str | None = None) -> str:
        # Append optional integration capabilities to the base prompt
        prompt = SYSTEM_BASE
        extra_caps = []
        try:
            from backend.services.todoist import todoist_enabled
            if todoist_enabled():
                extra_caps.append("- Todoist: you can add, list, and complete tasks (e.g. \"add a task\", \"what's on my list\").")
        except Exception:
            pass
        try:
            from backend.services.govee import govee_enabled
            if govee_enabled():
                extra_caps.append("- Smart home: you can control lights and devices (e.g. \"turn off the lights\", \"set brightness to 50%\").")
        except Exception:
            pass
        if extra_caps:
            prompt += "\n" + "\n".join(extra_caps)

        if memories:
            lines = "\n".join(f"- {m}" for m in memories)
            prompt += f"\n\nThings you know about the user:\n{lines}"
        if query:
            from backend.services.notes_watcher import notes_watcher_service
            if notes_watcher_service.active:
                notes = notes_watcher_service.search(query)
                if notes:
                    lines = "\n".join(f"[{n['source']}] {n['text']}" for n in notes)
                    prompt += f"\n\nContext from the user's personal notes (watched folders):\n{lines}"

            from backend.services.claude_memory import claude_memory_service
            claude_mems = claude_memory_service.search(query)
            if claude_mems:
                lines = "\n".join(f"[{m['source']}] {m['text']}" for m in claude_mems)
                prompt += f"\n\nContext from Claude Code memory files (supplementary):\n{lines}"
        if reminders:
            lines = "\n".join(
                f"- {r['text']}" + (f" (due: {r['due_time']})" if r.get("due_time") else "")
                for r in reminders
            )
            prompt += f"\n\nUpcoming reminders:\n{lines}"
        return prompt


memory_service = MemoryService()
