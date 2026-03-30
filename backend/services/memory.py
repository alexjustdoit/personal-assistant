import re
import sqlite3
import asyncio
import uuid
from pathlib import Path
from datetime import datetime

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

SYSTEM_BASE = """You are a helpful personal home assistant. You are concise, friendly, and direct.
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

    # --- Memory detection ---

    def extract_memory(self, text: str) -> str | None:
        for pattern in MEMORY_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip().rstrip(".")
        return None

    # --- System prompt builder ---

    def build_system_prompt(self, memories: list[str]) -> str:
        if not memories:
            return SYSTEM_BASE
        lines = "\n".join(f"- {m}" for m in memories)
        return f"{SYSTEM_BASE}\n\nThings you know about the user:\n{lines}"


memory_service = MemoryService()
