import tempfile
import os
from pathlib import Path
from backend.config import config


class STTService:
    def __init__(self):
        cfg = config.get("stt", {})
        self.enabled = cfg.get("enabled", True)
        self._model = None
        if self.enabled:
            self._model_size = cfg.get("model", "base")
            self._device = cfg.get("device", "cuda")
            self._compute_type = cfg.get("compute_type", "float16")

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
            )

    def transcribe(self, audio_bytes: bytes, suffix: str = ".webm") -> str:
        if not self.enabled:
            raise RuntimeError("STT is disabled in config")
        self._load()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name
        try:
            segments, _ = self._model.transcribe(tmp_path, beam_size=5)
            return "".join(seg.text for seg in segments).strip()
        finally:
            os.unlink(tmp_path)


stt_service = STTService()
