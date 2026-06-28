from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from auth import require_admin
from database import get_db
from models.crop import Crop, District
from models.crop_area import CropArea
from models.user import User
from schemas.admin import (
    AlertResponse,
    AlertsListResponse,
    CropEntryCreate,
    CropEntryResponse,
    CropEntryUpdate,
    CropResponse,
    DistrictResponse,
    PaginatedEntries,
)

router = APIRouter(prefix="/admin", tags=["Admin"])


def _compute_risk(area: int, prev: int) -> tuple[str, float]:
    if prev == 0:
        return "low", 0.0
    change = ((area - prev) / prev) * 100
    if change > 25:
        level = "high"
    elif change > 10:
        level = "medium"
    else:
        level = "low"
    return level, round(change, 1)


def _entry_to_response(entry: CropArea) -> CropEntryResponse:
    risk_level, change_pct = _compute_risk(entry.area_acres, entry.prev_year_acres)
    return CropEntryResponse(
        id=entry.id,
        district=entry.district.name,
        crop=entry.crop.name,
        season=entry.season,
        area_acres=entry.area_acres,
        prev_year_acres=entry.prev_year_acres,
        change_pct=change_pct,
        risk_level=risk_level,
        expected_yield=entry.expected_yield,
        data_source=entry.data_source,
        notes=entry.notes or "",
        entered_by=entry.user.name if entry.user else None,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


# ─── GET /admin/entries ───────────────────────────────────────────────────────

@router.get("/entries", response_model=PaginatedEntries)
def list_entries(
    crop: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    season: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    q = (
        db.query(CropArea)
        .join(Crop, CropArea.crop_id == Crop.id)
        .join(District, CropArea.district_id == District.id)
    )
    if crop:
        q = q.filter(Crop.name.ilike(f"%{crop}%"))
    if district:
        q = q.filter(District.name.ilike(f"%{district}%"))
    if season:
        q = q.filter(CropArea.season == season)

    total = q.count()
    entries = q.order_by(CropArea.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

    return PaginatedEntries(
        total=total,
        page=page,
        limit=limit,
        entries=[_entry_to_response(e) for e in entries],
    )


# ─── POST /admin/entries ──────────────────────────────────────────────────────

@router.post("/entries", response_model=CropEntryResponse, status_code=status.HTTP_201_CREATED)
def create_entry(
    payload: CropEntryCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    # Validate FK references exist
    district = db.query(District).filter(District.id == payload.district_id).first()
    if not district:
        raise HTTPException(status_code=404, detail=f"District {payload.district_id} not found.")
    crop = db.query(Crop).filter(Crop.id == payload.crop_id).first()
    if not crop:
        raise HTTPException(status_code=404, detail=f"Crop {payload.crop_id} not found.")

    # Duplicate check
    existing = (
        db.query(CropArea)
        .filter(
            CropArea.district_id == payload.district_id,
            CropArea.crop_id == payload.crop_id,
            CropArea.season == payload.season,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Entry already exists for {district.name} / {crop.name} / {payload.season}. Use PUT to update.",
        )

    entry = CropArea(
        district_id=payload.district_id,
        crop_id=payload.crop_id,
        season=payload.season,
        area_acres=payload.area_acres,
        prev_year_acres=payload.prev_year_acres,
        expected_yield=payload.expected_yield,
        data_source=payload.data_source,
        notes=payload.notes,
        entered_by=admin.id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _entry_to_response(entry)


# ─── PUT /admin/entries/{id} ──────────────────────────────────────────────────

@router.put("/entries/{entry_id}", response_model=CropEntryResponse)
def update_entry(
    entry_id: int,
    payload: CropEntryUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    entry = db.query(CropArea).filter(CropArea.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail=f"Entry with id {entry_id} not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(entry, field, value)
    entry.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(entry)
    return _entry_to_response(entry)


# ─── DELETE /admin/entries/{id} ───────────────────────────────────────────────

@router.delete("/entries/{entry_id}")
def delete_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    entry = db.query(CropArea).filter(CropArea.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail=f"Entry with id {entry_id} not found.")
    db.delete(entry)
    db.commit()
    return {"detail": "Entry deleted successfully."}


# ─── GET /admin/alerts ────────────────────────────────────────────────────────

@router.get("/alerts", response_model=AlertsListResponse)
def get_alerts(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    entries = db.query(CropArea).all()
    alerts = []

    for entry in entries:
        risk_level, change_pct = _compute_risk(entry.area_acres, entry.prev_year_acres)
        if risk_level in ("high", "medium"):
            if risk_level == "high":
                msg = f"Planted area is {abs(change_pct):.0f}% above last year. Price crash risk is significant."
            else:
                msg = f"Planted area is {abs(change_pct):.0f}% above last year. Monitor over next 4 weeks."

            alerts.append(AlertResponse(
                id=entry.id,
                district=entry.district.name,
                crop=entry.crop.name,
                risk_level=risk_level,
                change_pct=change_pct,
                area_acres=entry.area_acres,
                prev_year_acres=entry.prev_year_acres,
                season=entry.season,
                message=msg,
            ))

    # Sort: high first, then by change_pct descending
    alerts.sort(key=lambda a: (0 if a.risk_level == "high" else 1, -a.change_pct))

    return AlertsListResponse(total=len(alerts), alerts=alerts)


# ─── GET /admin/districts ─────────────────────────────────────────────────────

@router.get("/districts")
def list_districts(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    districts = db.query(District).order_by(District.name).all()
    return {"districts": [DistrictResponse.model_validate(d) for d in districts]}


# ─── GET /admin/crops ─────────────────────────────────────────────────────────

@router.get("/crops")
def list_crops(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    crops = db.query(Crop).all()
    return {"crops": [CropResponse.model_validate(c) for c in crops]}
