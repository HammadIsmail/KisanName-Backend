import os
from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# OpenAI TTS voices
VALID_VOICES = ("alloy", "ash", "coral", "echo", "fable", "onyx", "nova", "shimmer")
DEFAULT_VOICE = "nova"  # Clearest for Urdu text rendering


def synthesize_urdu(
    text: str,
    voice: str = DEFAULT_VOICE,
    model: str = "tts-1",
) -> bytes:
    """
    Convert Urdu text to MP3 audio using OpenAI TTS.
    Returns raw MP3 bytes.

    Models: tts-1 (faster, lower quality) | tts-1-hd (higher quality)
    Voices: alloy, ash, coral, echo, fable, onyx, nova, shimmer
    """
    if len(text) > 4096:
        raise ValueError("Text too long. Maximum 4096 characters per request.")

    if voice not in VALID_VOICES:
        voice = DEFAULT_VOICE

    response = _client.audio.speech.create(
        model=model,
        voice=voice,
        input=text,
        response_format="mp3",
    )

    return response.content
