"""Text-to-Speech API router — uses VieNeu-TTS (on-device Vietnamese + English)."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.services.vieneu_tts import list_voices as _list_voices
from app.services.vieneu_tts import synthesize

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tts")

# Single-thread pool — llama.cpp is NOT thread-safe; concurrent calls crash.
_executor = ThreadPoolExecutor(max_workers=1)


class TTSRequest(BaseModel):
    text: str
    voice: str = ""  # empty = default (Phạm Tuyên - Nam Miền Bắc)


@router.post("/speak")
async def speak(body: TTSRequest):
    """Convert text to speech using VieNeu-TTS. Returns audio/wav."""
    if not body.text or not body.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    if len(body.text) > 5000:
        raise HTTPException(status_code=400, detail="Text too long (max 5000 chars).")

    try:
        clean_text = body.text.strip()
        logger.info("TTS speak: voice=%r text=%r", body.voice or "(default)", clean_text[:120])

        loop = asyncio.get_running_loop()
        wav_bytes = await loop.run_in_executor(
            _executor, synthesize, clean_text, body.voice,
        )

        if not wav_bytes:
            raise HTTPException(status_code=500, detail="TTS produced no audio.")

        logger.info("TTS done: %d bytes", len(wav_bytes))

        return Response(
            content=wav_bytes,
            media_type="audio/wav",
            headers={"Cache-Control": "no-cache"},
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("VieNeu-TTS failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTS error: {exc}") from exc


@router.get("/voices")
async def get_voices():
    """List available VieNeu-TTS preset voices."""
    try:
        loop = asyncio.get_running_loop()
        voices = await loop.run_in_executor(_executor, _list_voices)
        return {"voices": voices}
    except Exception as exc:
        logger.error("Failed to list voices: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to list voices: {exc}",
        ) from exc
