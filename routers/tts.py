from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel

from auth import get_current_user
from database import get_db
from models.user import User
from services.speech import VALID_VOICES, DEFAULT_VOICE, synthesize_urdu
from sqlalchemy.orm import Session

router = APIRouter(tags=["TTS"])

VALID_MODELS = ("tts-1", "tts-1-hd")


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = DEFAULT_VOICE   # nova | alloy | ash | coral | echo | fable | onyx | shimmer
    model: Optional[str] = "tts-1"         # tts-1 (fast) | tts-1-hd (higher quality)


@router.post("/tts")
def tts(
    payload: TTSRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Convert Urdu text to MP3 audio using OpenAI TTS.
    Returns binary audio/mpeg.
    """
    if len(payload.text) > 4096:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text too long. Maximum 4096 characters per request.",
        )

    voice = payload.voice if payload.voice in VALID_VOICES else DEFAULT_VOICE
    model = payload.model if payload.model in VALID_MODELS else "tts-1"

    try:
        audio_bytes = synthesize_urdu(payload.text, voice=voice, model=model)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TTS service temporarily unavailable. Use browser fallback.",
        )

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline; filename=urdu_audio.mp3"},
    )
