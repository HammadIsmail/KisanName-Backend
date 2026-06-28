# schemas/__init__.py
from .auth import SignupRequest, LoginRequest, UserResponse, TokenResponse
from .query import QueryRequest
from .admin import (
    CropEntryCreate,
    CropEntryUpdate,
    CropEntryResponse,
    PaginatedEntries,
    AlertResponse,
    AlertsListResponse,
    DistrictResponse,
    CropResponse,
)

__all__ = [
    "SignupRequest", "LoginRequest", "UserResponse", "TokenResponse",
    "QueryRequest",
    "CropEntryCreate", "CropEntryUpdate", "CropEntryResponse",
    "PaginatedEntries", "AlertResponse", "AlertsListResponse",
    "DistrictResponse", "CropResponse",
]
