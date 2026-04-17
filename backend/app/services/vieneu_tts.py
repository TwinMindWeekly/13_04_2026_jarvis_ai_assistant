"""VieNeu-TTS service — on-device Vietnamese + English TTS with bilingual support.

Singleton wrapper around the VieNeu library (turbo mode, CPU-only).
Model is downloaded from HuggingFace on first use (~few hundred MB GGUF).

IMPORTANT: llama-cpp-python is NOT thread-safe — all inference calls are
serialized through _infer_lock.
"""

import io
import logging
import re
import threading

logger = logging.getLogger(__name__)

# All-caps words ≥4 chars → title case so TTS reads them as words,
# not letter-by-letter acronyms (e.g. JARVIS → Jarvis, HELLO → Hello).
# Short caps (AI, API, URL) are left as-is — likely real acronyms.
_ALLCAPS_WORD = re.compile(r"\b[A-Z]{4,}\b")

def _clean_text_for_tts(text: str) -> str:
    """Strip ALL markdown → plain text for TTS.

    Order matters: structural elements first, then inline formatting.
    """
    # 1. Code blocks first (remove entirely — not speakable)
    text = re.sub(r"```[\s\S]*?```", "", text)
    # 2. Images: ![alt](url) → remove
    text = re.sub(r"!\[.*?\]\(.+?\)", "", text)
    # 3. Links: [text](url) → text
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    # 4. HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # 5. Headings: ### text → text
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.M)
    # 6. Blockquote: "> " → remove
    text = re.sub(r"^\s*>\s*", "", text, flags=re.M)
    # 7. Horizontal rules
    text = re.sub(r"^-{3,}$", "", text, flags=re.M)
    # 8. Bullets at line start: "* ", "- ", "+ " → remove marker
    #    MUST run before bold/italic stripping (both use *)
    text = re.sub(r"^\s*[-*+]\s{1,4}", "", text, flags=re.M)
    # 9. Numbered lists: "1. " → "1, " (VieNeu reads "một,")
    text = re.sub(r"^\s*(\d+)\.\s+", r"\1, ", text, flags=re.M)
    # 10. Bold/italic: **text**, *text*, __text__, _text_ → text
    text = re.sub(r"\*{2}(.+?)\*{2}", r"\1", text)     # **bold**
    text = re.sub(r"\*(.+?)\*", r"\1", text)             # *italic*
    text = re.sub(r"__(.+?)__", r"\1", text)              # __bold__
    text = re.sub(r"_(.+?)_", r"\1", text)                # _italic_
    # 11. Inline code: `code` → code
    text = re.sub(r"`(.+?)`", r"\1", text)
    # 12. All-caps words ≥4 chars → title case (JARVIS → Jarvis)
    text = _ALLCAPS_WORD.sub(lambda m: m.group(0).capitalize(), text)
    # 13. Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

_tts_instance = None
_init_lock = threading.Lock()
_infer_lock = threading.Lock()  # serialize all inference — llama.cpp is not thread-safe

DEFAULT_VOICE = "Phạm Tuyên (Nam - Miền Bắc)"


def get_tts():
    """Lazy-init singleton. First call downloads models from HuggingFace."""
    global _tts_instance
    if _tts_instance is not None:
        return _tts_instance

    with _init_lock:
        if _tts_instance is not None:
            return _tts_instance

        from vieneu import Vieneu
        from app.core.config import settings

        device = (settings.vieneu_device or "cpu").lower()
        logger.info("Initializing VieNeu-TTS (turbo mode, device=%s)…", device)
        try:
            _tts_instance = Vieneu(mode="turbo", device=device)
        except Exception as exc:
            # GPU init can fail if the installed llama-cpp-python wheel lacks CUDA support.
            if device != "cpu":
                logger.warning(
                    "VieNeu-TTS init failed on device=%s (%s) — falling back to CPU.",
                    device, exc,
                )
                _tts_instance = Vieneu(mode="turbo", device="cpu")
            else:
                raise
        logger.info("VieNeu-TTS ready.")
        return _tts_instance


def synthesize(text: str, voice_id: str = "") -> bytes:
    """Synthesize text → WAV bytes (24 kHz, mono).

    VieNeu handles mixed Vietnamese + English natively — no language
    splitting needed.  All calls are serialized (llama.cpp constraint).
    """
    text = _clean_text_for_tts(text)

    tts = get_tts()

    # Empty voice_id → None → built-in default (fastest, no voice conditioning).
    # Named preset adds voice cloning codes which is significantly slower.
    voice_data = None
    if voice_id:
        try:
            voice_data = tts.get_preset_voice(voice_id)
        except Exception:
            logger.warning("Voice '%s' not found, using built-in default.", voice_id)

    import soundfile as sf

    with _infer_lock:
        audio = tts.infer(
            text=text,
            voice=voice_data,
            show_progress=False,
            apply_watermark=False,
        )

    buf = io.BytesIO()
    sf.write(buf, audio, 24000, format="WAV")
    buf.seek(0)
    return buf.read()


def list_voices() -> list[dict]:
    """Return available preset voices."""
    tts = get_tts()
    presets = tts.list_preset_voices()
    # presets is list of (description, voice_id) tuples
    return [{"id": vid, "label": desc} for desc, vid in presets]
