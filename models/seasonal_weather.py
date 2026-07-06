from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class SeasonalWeather(Base):
    __tablename__ = "seasonal_weather"

    id = Column(Integer, primary_key=True, index=True)
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=False)
    month = Column(Integer, nullable=False) # 1-12
    avg_temp_c = Column(Float, nullable=False)
    avg_rainfall_mm = Column(Float, nullable=False)

    district = relationship("District")
