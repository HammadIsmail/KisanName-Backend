# models/__init__.py — import all models so Base.metadata is fully populated
from .user import User
from .crop import Crop, District
from .crop_area import CropArea, PriceHistory
from .chat_session import ChatSession
from .query_log import QueryLog
from .seasonal_weather import SeasonalWeather

__all__ = ["User", "Crop", "District", "CropArea", "PriceHistory", "ChatSession", "QueryLog", "SeasonalWeather"]
