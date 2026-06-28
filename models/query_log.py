from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from database import Base


class QueryLog(Base):
    __tablename__ = "query_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=True, index=True)
    query_text = Column(Text, nullable=False)
    district = Column(String(100), nullable=True)
    crop = Column(String(50), nullable=True)
    risk_level = Column(String(20), nullable=True)
    recommended_crop = Column(String(100), nullable=True)
    response_ur = Column(Text, nullable=True)   # Full Urdu SSE stream
    response_en = Column(Text, nullable=True)   # Full English SSE stream
    created_at = Column(DateTime, default=datetime.utcnow)
