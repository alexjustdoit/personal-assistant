from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from backend.services.stt import stt_service
from backend.services.tts import tts_service

router = APIRouter(prefix="/api/voice")


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    if not stt_service.enabled:
        raise HTTPException(status_code=503, detail="STT is disabled in config")
    audio_bytes = await audio.read()
    suffix = "." + (audio.content_type or "audio/webm").split("/")[-1]
    try:
        text = stt_service.transcribe(audio_bytes, suffix=suffix)
        return {"text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SpeakRequest(BaseModel):
    text: str


@router.post("/speak")
async def speak(req: SpeakRequest):
    if not tts_service.enabled:
        raise HTTPException(status_code=503, detail="TTS is disabled in config")
    try:
        audio_bytes = tts_service.synthesize(req.text)
        return Response(content=audio_bytes, media_type="audio/wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def voice_status():
    return {
        "stt": stt_service.enabled,
        "tts": tts_service.enabled,
    }
