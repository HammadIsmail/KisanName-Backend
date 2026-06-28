from sqlalchemy import Column, Integer, String
from database import Base


class Crop(Base):
    __tablename__ = "crops"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)  # 'Potato' | 'Onion' | 'Wheat'


class District(Base):
    __tablename__ = "districts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    province = Column(String(50), nullable=False)
