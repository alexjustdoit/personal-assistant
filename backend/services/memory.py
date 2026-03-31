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

SYSTEM_BASE = """You are a helpful personal assistant. You are concise, friendly, and direct.
When you don't know something, say so.
When the user asks you to remember something, confirm that you've noted it."""


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
                "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [{"role": r, "content": c} for r, c in reversed(rows)]

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

    def get_chats(self) -> list[dict]:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute("""
                SELECT
                    m.session_id,
                    MIN(m.timestamp) AS created_at,
                    MAX(m.timestamp) AS last_active,
                    (SELECT content FROM messages
                     WHERE session_id = m.session_id AND role = 'user'
                     ORDER BY id LIMIT 1) AS name
                FROM messages m
                GROUP BY m.session_id
                ORDER BY last_active DESC
            """).fetchall()
        return [
            {"id": r[0], "name": r[3] or "New chat", "created_at": r[1], "last_active": r[2]}
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
        prompt = SYSTEM_BASE
        if memories:
            lines = "\n".join(f"- {m}" for m in memories)
            prompt += f"\n\nThings you know about the user:\n{lines}"
        if query:
            from backend.services.claude_memory import claude_memory_service
            claude_mems = claude_memory_service.search(query)
            if claude_mems:
                lines = "\n".join(f"- {m}" for m in claude_mems)
                prompt += f"\n\nContext from the user's work sessions:\n{lines}"
        if reminders:
            lines = "\n".join(
                f"- {r['text']}" + (f" (due: {r['due_time']})" if r.get("due_time") else "")
                for r in reminders
            )
            prompt += f"\n\nUpcoming reminders:\n{lines}"
        return prompt


memory_service = MemoryService()
