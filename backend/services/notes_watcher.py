import hashlib
from pathlib import Path

NOTES_COLLECTION = "user_notes"
TEXT_SUFFIXES = {".md", ".txt"}


class NotesWatcherService:
    def __init__(self):
        self._collection = None
        self._observers = []
        self._watched_paths: list[str] = []

    def start(self, paths: list[str]):
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        service = self

        class _Handler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory and Path(event.src_path).suffix in TEXT_SUFFIXES:
                    service._ingest_file(Path(event.src_path))

            def on_modified(self, event):
                if not event.is_directory and Path(event.src_path).suffix in TEXT_SUFFIXES:
                    service._ingest_file(Path(event.src_path))

            def on_deleted(self, event):
                if not event.is_directory:
                    service._remove_file(Path(event.src_path))

        for path_str in paths:
            path = Path(path_str).expanduser()
            if not path.exists():
                print(f"[NotesWatcher] Path not found: {path_str}")
                continue
            self._watched_paths.append(str(path))
            self._ingest_all(path)
            observer = Observer()
            observer.schedule(_Handler(), str(path), recursive=True)
            observer.start()
            self._observers.append(observer)
            print(f"[NotesWatcher] Watching {path}")

    def stop(self):
        for obs in self._observers:
            obs.stop()
            obs.join()
        self._observers = []

    def _get_collection(self):
        if self._collection is None:
            import chromadb
            from backend.services.memory import CHROMA_PATH
            client = chromadb.PersistentClient(path=CHROMA_PATH)
            self._collection = client.get_or_create_collection(NOTES_COLLECTION)
        return self._collection

    def _doc_id(self, path: Path) -> str:
        return hashlib.sha1(str(path.resolve()).encode()).hexdigest()[:20]

    def _ingest_all(self, path: Path):
        for f in path.rglob("*"):
            if f.is_file() and f.suffix in TEXT_SUFFIXES:
                self._ingest_file(f)

    def _ingest_file(self, path: Path):
        try:
            text = path.read_text(encoding="utf-8").strip()
            if not text:
                return
            if path.suffix == ".md" and text.startswith("---"):
                end = text.find("---", 3)
                if end != -1:
                    text = text[end + 3:].strip()
            if not text:
                return
            doc_id = self._doc_id(path)
            col = self._get_collection()
            meta = [{"path": str(path), "filename": path.name, "stem": path.stem}]
            existing = col.get(ids=[doc_id])
            if existing["ids"]:
                col.update(ids=[doc_id], documents=[text], metadatas=meta)
            else:
                col.add(ids=[doc_id], documents=[text], metadatas=meta)
            print(f"[NotesWatcher] Ingested: {path.name}")
        except Exception as e:
            print(f"[NotesWatcher] Error ingesting {path}: {e}")

    def _remove_file(self, path: Path):
        try:
            self._get_collection().delete(ids=[self._doc_id(path)])
            print(f"[NotesWatcher] Removed: {path.name}")
        except Exception as e:
            print(f"[NotesWatcher] Error removing {path}: {e}")

    def search(self, query: str, n: int = 3) -> list[dict]:
        try:
            col = self._get_collection()
            if col.count() == 0:
                return []
            results = col.query(
                query_texts=[query],
                n_results=min(n, col.count()),
                include=["documents", "metadatas"],
            )
            docs = results["documents"][0] if results["documents"] else []
            metas = results["metadatas"][0] if results["metadatas"] else []
            return [
                {"source": m.get("filename", "?"), "path": m.get("path", ""), "text": doc}
                for m, doc in zip(metas, docs)
            ]
        except Exception:
            return []

    @property
    def active(self) -> bool:
        return len(self._observers) > 0


notes_watcher_service = NotesWatcherService()
