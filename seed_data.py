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

CROPS = ["Potato", "Onion", "Wheat"]

# PBS-inspired sample crop area data
CROP_AREA_DATA = [
    # (district_name, crop_name, season, area_acres, prev_year_acres, expected_yield, source)
    ("Sahiwal", "Potato", "Rabi 2025-26", 5200, 3800, 180, "PBS field survey"),
    ("Okara", "Potato", "Rabi 2025-26", 4800, 4200, 175, "Patwari report"),
    ("Faisalabad", "Onion", "Rabi 2025-26", 3100, 2740, 120, "PBS field survey"),
    ("Multan", "Onion", "Kharif 2025", 2800, 2600, 110, "District agriculture dept"),
    ("Lahore", "Wheat", "Rabi 2025-26", 12000, 11500, 35, "PBS field survey"),
    ("Gujranwala", "Wheat", "Rabi 2025-26", 18500, 17800, 38, "PBS field survey"),
    ("Sheikhupura", "Potato", "Rabi 2025-26", 3200, 3100, 165, "Patwari report"),
    ("Rahim Yar Khan", "Wheat", "Rabi 2025-26", 22000, 21000, 36, "PBS field survey"),
]

# Price history base prices (PKR/maund)
BASE_PRICES = {
    "Potato": 1200,
    "Onion": 800,
    "Wheat": 2200,
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

        # ── Crop Area Data ─────────────────────────────────────────────────
        for d_name, c_name, season, area, prev, yield_, source in CROP_AREA_DATA:
            d = district_map.get(d_name)
            c = crop_map.get(c_name)
            if not d or not c:
                continue

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
                    prev_year_acres=prev,
                    expected_yield=yield_,
                    data_source=source,
                    entered_by=admin.id,
                )
                db.add(entry)
                print(f"  ✓ CropArea: {d_name}/{c_name}/{season}")

        db.commit()

        # ── Price History (12 months per crop/district combo) ──────────────
        today = date.today()
        for d_name, c_name, *_ in CROP_AREA_DATA:
            d = district_map.get(d_name)
            c = crop_map.get(c_name)
            if not d or not c:
                continue

            existing_count = (
                db.query(PriceHistory)
                .filter(PriceHistory.district_id == d.id, PriceHistory.crop_id == c.id)
                .count()
            )
            if existing_count > 0:
                continue

            base = BASE_PRICES[c_name]
            for i in range(12):
                record_date = today - timedelta(days=30 * i)
                # Slight random fluctuation ±15%
                variation = random.uniform(-0.15, 0.15)
                price = int(base * (1 + variation))
                ph = PriceHistory(
                    crop_id=c.id,
                    district_id=d.id,
                    price_pkr=price,
                    recorded_at=record_date,
                )
                db.add(ph)
            print(f"  ✓ PriceHistory: {d_name}/{c_name} (12 months)")

        db.commit()
        print("\n✅ Seed complete!")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("🌱 Seeding KisanNama database...\n")
    seed()
