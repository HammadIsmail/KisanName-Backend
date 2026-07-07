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


async def _synthesize_async(text: str, voice: str) -> bytes:
    """Internal async helper — streams edge-tts output into bytes."""
    communicate = edge_tts.Communicate(text, voice)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    return buf.getvalue()


def synthesize_urdu(
    text: str,
    voice: str = DEFAULT_VOICE,
    model: str = "tts-1",   # kept for API compatibility — ignored by edge-tts
) -> bytes:
    """
    Convert text to MP3 audio using Microsoft Neural TTS.
    Returns raw MP3 bytes.

    voice options: ur-PK-UzmaNeural (female) | ur-PK-AsadNeural (male)
    """
    if len(text) > 4096:
        raise ValueError("Text too long. Maximum 4096 characters per request.")

    if voice not in VALID_VOICES:
        voice = DEFAULT_VOICE

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Running inside an existing event loop (FastAPI) — use a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _synthesize_async(text, voice))
                return future.result()
        else:
            return loop.run_until_complete(_synthesize_async(text, voice))
    except Exception as e:
        raise RuntimeError(f"TTS synthesis failed: {e}") from e
