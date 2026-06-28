import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator


class SignupRequest(BaseModel):
    name: str
    phone: str
    password: str
    role: str = "farmer"

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not re.match(r"^03\d{9}$", v):
            raise ValueError("Phone number must be 11 digits starting with 03")
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("farmer", "admin"):
            raise ValueError("Role must be 'farmer' or 'admin'")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class LoginRequest(BaseModel):
    phone: str
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    phone: str
    role: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    id: int
    name: str
    phone: Optional[str] = None
    role: str
    token: str
