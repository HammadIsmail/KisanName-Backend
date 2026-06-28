"""
Shared DB tools used by CrewAI agents.
All tools receive a SQLAlchemy session injected at crew runtime.
"""
from typing import Optional
from crewai.tools import tool
from sqlalchemy.orm import Session


def make_tools(db: Session):
    """Factory — returns tool functions bound to the given DB session."""

    @tool("get_crop_area")
    def get_crop_area(district: str, crop: str, season: Optional[str] = None) -> dict:
        """
        Fetches crop area data from the database for a given district, crop, and season.
        Returns current area, previous year area, and basic metadata.
        If season is not provided, returns the most recent entry.
        """
        from models.crop_area import CropArea
        from models.crop import Crop, District as DistrictModel

        query = (
            db.query(CropArea)
            .join(DistrictModel, CropArea.district_id == DistrictModel.id)
            .join(Crop, CropArea.crop_id == Crop.id)
            .filter(DistrictModel.name.ilike(f"%{district}%"))
            .filter(Crop.name.ilike(f"%{crop}%"))
        )
        if season:
            query = query.filter(CropArea.season == season)

        entry = query.order_by(CropArea.created_at.desc()).first()

        if not entry:
            return {
                "found": False,
                "district": district,
                "crop": crop,
                "message": f"No data found for {crop} in {district}",
            }

        change_pct = round(
            ((entry.area_acres - entry.prev_year_acres) / entry.prev_year_acres) * 100, 1
        ) if entry.prev_year_acres else 0

        return {
            "found": True,
            "district": entry.district.name,
            "crop": entry.crop.name,
            "season": entry.season,
            "area_acres": entry.area_acres,
            "prev_year_acres": entry.prev_year_acres,
            "change_pct": change_pct,
            "expected_yield": entry.expected_yield,
        }

    @tool("get_price_history")
    def get_price_history(crop: str, district: str) -> dict:
        """
        Fetches price history for a crop in a district (last 3 seasons of data).
        Returns list of prices sorted by date descending, and trend (rising/stable/falling).
        """
        from models.crop_area import PriceHistory
        from models.crop import Crop, District as DistrictModel

        records = (
            db.query(PriceHistory)
            .join(Crop, PriceHistory.crop_id == Crop.id)
            .join(DistrictModel, PriceHistory.district_id == DistrictModel.id)
            .filter(Crop.name.ilike(f"%{crop}%"))
            .filter(DistrictModel.name.ilike(f"%{district}%"))
            .order_by(PriceHistory.recorded_at.desc())
            .limit(12)  # ~3 seasons of monthly data
            .all()
        )

        if not records:
            return {
                "found": False,
                "crop": crop,
                "district": district,
                "message": "No price history found.",
            }

        prices = [r.price_pkr for r in records]
        last_price = prices[0]
        oldest_price = prices[-1]

        if oldest_price == 0:
            trend = "stable"
        else:
            change = ((last_price - oldest_price) / oldest_price) * 100
            if change > 5:
                trend = "rising"
            elif change < -5:
                trend = "falling"
            else:
                trend = "stable"

        return {
            "found": True,
            "crop": crop,
            "district": district,
            "last_price_pkr": last_price,
            "prices": prices,
            "trend": trend,
            "change_pct": round(((last_price - oldest_price) / oldest_price) * 100, 1) if oldest_price else 0,
        }

    return get_crop_area, get_price_history
