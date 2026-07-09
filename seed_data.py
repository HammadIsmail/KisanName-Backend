"""
Seed script — run once to populate reference data and admin account.
Usage:  cd backend && python seed_data.py
"""
from datetime import date, timedelta
import random
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal, init_db
from models.crop import Crop, District
from models.crop_area import CropArea, PriceHistory
from models.user import User
from models.seasonal_weather import SeasonalWeather
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DISTRICTS = [
    ("Sahiwal", "Punjab"),
    ("Okara", "Punjab"),
    ("Faisalabad", "Punjab"),
    ("Multan", "Punjab"),
    ("Lahore", "Punjab"),
    ("Gujranwala", "Punjab"),
    ("Sheikhupura", "Punjab"),
    ("Rahim Yar Khan", "Punjab"),
]

# Expanded list to give the AI strategy alternatives
CROPS = ["Potato", "Onion", "Wheat", "Maize", "Sunflower", "Canola", "Sugarcane"]

# 4 years of history (3 previous seasons + current season)
SEASONS = ["Rabi 2022-23", "Rabi 2023-24", "Rabi 2024-25", "Rabi 2025-26"]

BASE_PRICES = {
    "Potato": 1200,
    "Onion": 800,
    "Wheat": 2200,
    "Maize": 1500,
    "Sunflower": 3500,
    "Canola": 4000,
    "Sugarcane": 300,
}

BASE_YIELDS = {
    "Potato": 180,
    "Onion": 120,
    "Wheat": 35,
    "Maize": 80,
    "Sunflower": 20,
    "Canola": 18,
    "Sugarcane": 600,
}


def seed():
    init_db()
    db = SessionLocal()

    try:
        # ── Crops ──────────────────────────────────────────────────────────
        crop_map = {}
        for crop_name in CROPS:
            existing = db.query(Crop).filter(Crop.name == crop_name).first()
            if not existing:
                c = Crop(name=crop_name)
                db.add(c)
                db.flush()
                crop_map[crop_name] = c
                print(f"  ✓ Crop: {crop_name}")
            else:
                crop_map[crop_name] = existing

        # ── Districts ──────────────────────────────────────────────────────
        district_map = {}
        for d_name, province in DISTRICTS:
            existing = db.query(District).filter(District.name == d_name).first()
            if not existing:
                d = District(name=d_name, province=province)
                db.add(d)
                db.flush()
                district_map[d_name] = d
                print(f"  ✓ District: {d_name}")
            else:
                district_map[d_name] = existing

        db.commit()

        # ── Admin user ─────────────────────────────────────────────────────
        admin_phone = "03000000001"
        existing_admin = db.query(User).filter(User.phone == admin_phone).first()
        if not existing_admin:
            admin = User(
                name="Ahmad Raza",
                phone=admin_phone,
                password=pwd_context.hash("admin123"),
                role="admin",
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
            print(f"  ✓ Admin user: phone={admin_phone}, password=admin123")
        else:
            admin = existing_admin
            print("  ℹ Admin user already exists")

        # ── Crop Area Data (4 Years, All crops, All districts) ─────────────
        for d_name, province in DISTRICTS:
            d = district_map.get(d_name)
            for c_name in CROPS:
                c = crop_map.get(c_name)
                
                # Base area for this specific district/crop combo
                base_area = random.randint(1000, 15000)
                
                prev_area = base_area
                for season in SEASONS:
                    # Randomize current area by -10% to +15% from prev year
                    variation = random.uniform(-0.10, 0.15)
                    area = int(prev_area * (1 + variation))
                    
                    expected_yield = int(BASE_YIELDS[c_name] * random.uniform(0.9, 1.1))
                    
                    existing = (
                        db.query(CropArea)
                        .filter(
                            CropArea.district_id == d.id,
                            CropArea.crop_id == c.id,
                            CropArea.season == season,
                        )
                        .first()
                    )
                    
                    if not existing:
                        entry = CropArea(
                            district_id=d.id,
                            crop_id=c.id,
                            season=season,
                            area_acres=area,
                            prev_year_acres=prev_area,
                            expected_yield=expected_yield,
                            data_source="PBS simulated data",
                            entered_by=admin.id,
                        )
                        db.add(entry)
                    
                    prev_area = area # Next season's prev area is this season's area
                
                print(f"  ✓ CropArea: {d_name} - {c_name} (4 seasons)")

        db.commit()

        # ── Price History (36 months per crop/district combo) ──────────────
        today = date.today()
        for d_name, province in DISTRICTS:
            d = district_map.get(d_name)
            for c_name in CROPS:
                c = crop_map.get(c_name)
                
                existing_count = (
                    db.query(PriceHistory)
                    .filter(PriceHistory.district_id == d.id, PriceHistory.crop_id == c.id)
                    .count()
                )
                
                # If existing count is less than 36, clear and re-seed
                if existing_count < 36:
                    db.query(PriceHistory).filter(PriceHistory.district_id == d.id, PriceHistory.crop_id == c.id).delete()
                    
                    base = BASE_PRICES[c_name]
                    current_price = base
                    for i in range(36):
                        record_date = today - timedelta(days=30 * i)
                        # Prices drift monthly
                        variation = random.uniform(-0.05, 0.06)
                        current_price = int(current_price * (1 + variation))
                        
                        ph = PriceHistory(
                            crop_id=c.id,
                            district_id=d.id,
                            price_pkr=current_price,
                            recorded_at=record_date,
                        )
                        db.add(ph)
                    print(f"  ✓ PriceHistory: {d_name} - {c_name} (36 months)")

        db.commit()

        # ── Seasonal Weather (12 months per district) ──────────────────────
        # Schema only supports month 1-12 (averages), not full historical weather
        for d_name, province in DISTRICTS:
            d = district_map.get(d_name)
            
            existing_count = (
                db.query(SeasonalWeather)
                .filter(SeasonalWeather.district_id == d.id)
                .count()
            )
            
            if existing_count != 12:
                # Clear existing if misconfigured
                db.query(SeasonalWeather).filter(SeasonalWeather.district_id == d.id).delete()

                for month in range(1, 13):
                    # Fake data: hotter in summer (Jun-Aug), some rain in monsoon (Jul-Sep)
                    if 5 <= month <= 8:
                        temp = random.uniform(30.0, 42.0)
                    else:
                        temp = random.uniform(12.0, 28.0)
                    
                    if 7 <= month <= 9:
                        rain = random.uniform(50.0, 200.0)
                    else:
                        rain = random.uniform(0.0, 30.0)
                    
                    sw = SeasonalWeather(
                        district_id=d.id,
                        month=month,
                        avg_temp_c=round(temp, 1),
                        avg_rainfall_mm=round(rain, 1),
                    )
                    db.add(sw)
                print(f"  ✓ SeasonalWeather: {d_name} (12 monthly averages)")

        db.commit()
        print("\n✅ Seed complete with comprehensive historical data!")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("🌱 Seeding KisanNama database with comprehensive historical data...\n")
    seed()
