from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class CropArea(Base):
    __tablename__ = "crop_area"

    id = Column(Integer, primary_key=True, index=True)
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=False)
    crop_id = Column(Integer, ForeignKey("crops.id"), nullable=False)
    season = Column(String(20), nullable=False)        # e.g. 'Rabi 2025-26'
    area_acres = Column(Integer, nullable=False)
    prev_year_acres = Column(Integer, nullable=False)
    expected_yield = Column(Integer, nullable=True)    # maunds/acre
    data_source = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    entered_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    district = relationship("District")
    crop = relationship("Crop")
    user = relationship("User")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    crop_id = Column(Integer, ForeignKey("crops.id"), nullable=False)
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=False)
    price_pkr = Column(Integer, nullable=False)        # PKR per maund
    recorded_at = Column(Date, nullable=False)

    crop = relationship("Crop")
    district = relationship("District")
