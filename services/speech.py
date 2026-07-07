"""
TTS service using edge-tts (Microsoft Neural Voices).
No API key required — free, high quality, supports Urdu natively.

Available Urdu voices:
  ur-PK-UzmaNeural   — Female (default, clear & natural)
  ur-PK-AsadNeural   — Male
"""
import asyncio
import io
import edge_tts

# Urdu neural voices available via edge-tts
VALID_VOICES = ("ur-PK-UzmaNeural", "ur-PK-AsadNeural")
DEFAULT_VOICE = "ur-PK-UzmaNeural"


async def synthesize_urdu_async(text: str, voice: str = DEFAULT_VOICE) -> bytes:
    """
    Async version — call this directly from async FastAPI endpoints via await.
    Convert text to MP3 audio using Microsoft Neural TTS (edge-tts).
    Returns raw MP3 bytes.
    """
    if len(text) > 4096:
        raise ValueError("Text too long. Maximum 4096 characters per request.")

    if voice not in VALID_VOICES:
        voice = DEFAULT_VOICE

    communicate = edge_tts.Communicate(text, voice)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    audio = buf.getvalue()
    if not audio:
        raise RuntimeError("edge-tts returned empty audio")
    return audio


def synthesize_urdu(
    text: str,
    voice: str = DEFAULT_VOICE,
    model: str = "tts-1",   # kept for API compatibility — ignored by edge-tts
) -> bytes:
    """
    Sync wrapper — kept for backward compatibility.
    Prefer synthesize_urdu_async() in async contexts.
    """
    return asyncio.run(synthesize_urdu_async(text, voice))
