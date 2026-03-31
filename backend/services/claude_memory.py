from pathlib import Path

CHROMA_COLLECTION = "claude_code_memory"


class ClaudeMemoryService:
    def __init__(self):
        self._collection = None
        self._observer = None

    def start(self, watch_path: str):
        path = Path(watch_path)
        if not path.exists():
            print(f"[ClaudeMemory] Path not found: {watch_path}")
            return

        self._ingest_all(path)

        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        service = self

        class _Handler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory and event.src_path.endswith(".md"):
                    p = Path(event.src_path)
                    if p.name != "MEMORY.md":
                        service._ingest_file(p)

            def on_modified(self, event):
                if not event.is_directory and event.src_path.endswith(".md"):
                    p = Path(event.src_path)
                    if p.name != "MEMORY.md":
                        service._ingest_file(p)

            def on_deleted(self, event):
                if not event.is_directory and event.src_path.endswith(".md"):
                    service._remove_file(Path(event.src_path))

        self._observer = Observer()
        self._observer.schedule(_Handler(), str(path), recursive=True)
        self._observer.start()
        print(f"[ClaudeMemory] Watching {watch_path}")

    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join()

    def _get_collection(self):
        if self._collection is None:
            import chromadb
            from backend.services.memory import CHROMA_PATH
            client = chromadb.PersistentClient(path=CHROMA_PATH)
            self._collection = client.get_or_create_collection(CHROMA_COLLECTION)
        return self._collection

    def _ingest_all(self, path: Path):
        for md_file in path.rglob("*.md"):
            if md_file.name != "MEMORY.md":
                self._ingest_file(md_file)

    def _ingest_file(self, path: Path):
        try:
            text = path.read_text(encoding="utf-8").strip()
            if not text:
                return
            # Strip YAML frontmatter
            if text.startswith("---"):
                end = text.find("---", 3)
                if end != -1:
                    text = text[end + 3:].strip()
            if not text:
                return
            doc_id = path.stem
            col = self._get_collection()
            existing = col.get(ids=[doc_id])
            if existing["ids"]:
                col.update(ids=[doc_id], documents=[text])
            else:
                col.add(ids=[doc_id], documents=[text])
            print(f"[ClaudeMemory] Ingested: {path.name}")
        except Exception as e:
            print(f"[ClaudeMemory] Error ingesting {path}: {e}")

    def _remove_file(self, path: Path):
        try:
            self._get_collection().delete(ids=[path.stem])
            print(f"[ClaudeMemory] Removed: {path.name}")
        except Exception as e:
            print(f"[ClaudeMemory] Error removing {path.stem}: {e}")

    def search(self, query: str, n: int = 3) -> list[dict]:
        """Returns list of {source, text} dicts ordered by relevance."""
        try:
            col = self._get_collection()
            count = col.count()
            if count == 0:
                return []
            results = col.query(query_texts=[query], n_results=min(n, count))
            docs = results["documents"][0] if results["documents"] else []
            ids = results["ids"][0] if results["ids"] else []
            return [{"source": sid, "text": doc} for sid, doc in zip(ids, docs)]
        except Exception:
            return []


claude_memory_service = ClaudeMemoryService()
