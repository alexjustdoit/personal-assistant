import io
import numpy as np
from backend.config import config


class TTSService:
    def __init__(self):
        cfg = config.get("tts", {})
        self.enabled = cfg.get("enabled", True)
        self.voice = cfg.get("voice", "af_heart")
        self.speed = cfg.get("speed", 1.0)
        self._pipeline = None

    def _load(self):
        if self._pipeline is None:
            from kokoro import KPipeline
            self._pipeline = KPipeline(lang_code="a")  # 'a' = American English

    def synthesize(self, text: str) -> bytes:
        if not self.enabled:
            raise RuntimeError("TTS is disabled in config")
        self._load()
        import soundfile as sf
        chunks = []
        for _, _, audio in self._pipeline(text, voice=self.voice, speed=self.speed):
            chunks.append(audio)
        audio = np.concatenate(chunks)
        buf = io.BytesIO()
        sf.write(buf, audio, 24000, format="WAV")
        buf.seek(0)
        return buf.read()


tts_service = TTSService()
