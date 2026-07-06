"""
Shared DB tools used by CrewAI agents.
All tools receive a SQLAlchemy session injected at crew runtime.
"""
from typing import Optional
from crewai.tools import tool
from sqlalchemy.orm import Session
from sqlalchemy import func

def make_tools(db: Session):
    """Factory — returns tool functions bound to the given DB session."""

    @tool("get_crop_area_summary")
    def get_crop_area_summary(district: str, crop: str) -> str:
        """
        Fetches crop area data from the database for a given district and crop.
        Returns a text summary containing this season's area, last season's area, 
        3-year average, and percentage change vs 3-year average.
        """
        from models.crop_area import CropArea
        from models.crop import Crop, District as DistrictModel

        # Subquery to get the last 3 seasons of data
        subq = (
            db.query(CropArea)
            .join(DistrictModel, CropArea.district_id == DistrictModel.id)
            .join(Crop, CropArea.crop_id == Crop.id)
            .filter(DistrictModel.name.ilike(f"%{district}%"))
            .filter(Crop.name.ilike(f"%{crop}%"))
            .order_by(CropArea.created_at.desc())
            .limit(3)
            .subquery()
        )

        avg_area = db.query(func.avg(subq.c.area_acres)).scalar()

        # Get latest 2 to find this season and last season
        recent_records = (
            db.query(CropArea)
            .join(DistrictModel, CropArea.district_id == DistrictModel.id)
            .join(Crop, CropArea.crop_id == Crop.id)
            .filter(DistrictModel.name.ilike(f"%{district}%"))
            .filter(Crop.name.ilike(f"%{crop}%"))
            .order_by(CropArea.created_at.desc())
            .limit(2)
            .all()
        )

        if not recent_records:
            return f"No crop area data found for {crop} in {district}."

        this_season_area = recent_records[0].area_acres
        last_season_area = recent_records[1].area_acres if len(recent_records) > 1 else recent_records[0].prev_year_acres
        avg_area = float(avg_area) if avg_area else float(this_season_area)

        change_pct = round(((this_season_area - avg_area) / avg_area) * 100, 1) if avg_area else 0

        return (
            f"Crop Area Summary for {crop} in {district}:\n"
            f"- This season's area: {this_season_area} acres\n"
            f"- Last season's area: {last_season_area} acres\n"
            f"- 3-year average area: {avg_area:.1f} acres\n"
            f"- Percentage change vs 3-year average: {change_pct}%"
        )

    @tool("assess_risk")
    def assess_risk(change_pct: float) -> str:
        """
        Assesses the risk level based on the percentage change versus the 3-year average.
        Returns a text summary indicating HIGH, MEDIUM, or LOW risk.
        """
        if change_pct > 25:
            level = "HIGH"
        elif change_pct > 10:
            level = "MEDIUM"
        else:
            level = "LOW"
            
        return f"Risk Level: {level} (based on {change_pct}% change vs 3-year average)"

    @tool("get_market_trend_summary")
    def get_market_trend_summary(crop: str, district: str) -> str:
        """
        Fetches price history for a crop in a district.
        Returns a text summary of recent price, 3-season average, min/max range, and trend direction.
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
            return f"No price history found for {crop} in {district}."

        prices = [r.price_pkr for r in records]
        recent_price = prices[0]
        avg_price = sum(prices) / len(prices)
        min_price = min(prices)
        max_price = max(prices)

        change_vs_avg = ((recent_price - avg_price) / avg_price) * 100 if avg_price else 0
        if change_vs_avg > 5:
            trend = "RISING"
        elif change_vs_avg < -5:
            trend = "FALLING"
        else:
            trend = "STABLE"

        return (
            f"Market Trend Summary for {crop} in {district}:\n"
            f"- Recent price: {recent_price} PKR/maund\n"
            f"- 3-season average price: {avg_price:.1f} PKR/maund\n"
            f"- Price range (min/max): {min_price} - {max_price} PKR/maund\n"
            f"- Trend direction: {trend}"
        )

    return get_crop_area_summary, assess_risk, get_market_trend_summary
