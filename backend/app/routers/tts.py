"""Text-to-Speech API router — uses Edge TTS (Microsoft Neural voices, free)."""

import io
import logging

import edge_tts
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tts")

# Voice mapping — Edge TTS neural voices
VOICE_MAP = {
    "vi": "vi-VN-HoaiMyNeural",
    "en": "en-US-AriaNeural",
}


class TTSRequest(BaseModel):
    text: str
    language: str = "vi"  # "vi" or "en"
    rate: str = "+0%"     # speed adjustment, e.g. "+10%", "-5%"


@router.post("/speak")
async def speak(body: TTSRequest):
    """Convert text to speech using Edge TTS. Returns audio/mpeg stream."""
    if not body.text or not body.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    if len(body.text) > 5000:
        raise HTTPException(status_code=400, detail="Text too long (max 5000 chars).")

    voice = VOICE_MAP.get(body.language, VOICE_MAP["vi"])

    try:
        communicate = edge_tts.Communicate(body.text, voice, rate=body.rate)
        audio_buffer = io.BytesIO()

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])

        audio_buffer.seek(0)

        if audio_buffer.getbuffer().nbytes == 0:
            raise HTTPException(status_code=500, detail="TTS produced no audio.")

        return StreamingResponse(
            audio_buffer,
            media_type="audio/mpeg",
            headers={"Cache-Control": "no-cache"},
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Edge TTS failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTS error: {exc}") from exc


@router.get("/voices")
async def list_voices():
    """List available Edge TTS voices."""
    voices = await edge_tts.list_voices()
    vi_voices = [v for v in voices if v["Locale"].startswith("vi")]
    en_voices = [v for v in voices if v["Locale"].startswith("en-US")]
    return {
        "vi": [{"name": v["ShortName"], "gender": v["Gender"]} for v in vi_voices],
        "en": [{"name": v["ShortName"], "gender": v["Gender"]} for v in en_voices],
    }
