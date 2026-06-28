from typing import Optional
from pydantic import BaseModel, field_validator


class QueryRequest(BaseModel):
    text: str
    district: Optional[str] = None
    crop: Optional[str] = None
    land_acres: Optional[float] = None
    session_id: Optional[int] = None  # if None, a new session is created

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Query text cannot be empty.")
        return v.strip()

    @field_validator("crop")
    @classmethod
    def validate_crop(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in ("Potato", "Onion", "Wheat"):
            raise ValueError("crop must be one of: Potato, Onion, Wheat")
        return v
