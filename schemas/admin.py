from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, field_validator


class CropEntryCreate(BaseModel):
    district_id: int
    crop_id: int
    season: str
    area_acres: int
    prev_year_acres: int
    expected_yield: Optional[int] = None
    data_source: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("area_acres", "prev_year_acres")
    @classmethod
    def validate_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("must be greater than 0")
        return v


class CropEntryUpdate(BaseModel):
    area_acres: Optional[int] = None
    prev_year_acres: Optional[int] = None
    expected_yield: Optional[int] = None
    data_source: Optional[str] = None
    notes: Optional[str] = None
    season: Optional[str] = None


class CropEntryResponse(BaseModel):
    id: int
    district: str
    crop: str
    season: str
    area_acres: int
    prev_year_acres: int
    change_pct: float
    risk_level: str
    expected_yield: Optional[int] = None
    data_source: Optional[str] = None
    notes: Optional[str] = None
    entered_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaginatedEntries(BaseModel):
    total: int
    page: int
    limit: int
    entries: List[CropEntryResponse]


class AlertResponse(BaseModel):
    id: int
    district: str
    crop: str
    risk_level: str
    change_pct: float
    area_acres: int
    prev_year_acres: int
    season: str
    message: str


class AlertsListResponse(BaseModel):
    total: int
    alerts: List[AlertResponse]


class DistrictResponse(BaseModel):
    id: int
    name: str
    province: str

    model_config = {"from_attributes": True}


class CropResponse(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}
