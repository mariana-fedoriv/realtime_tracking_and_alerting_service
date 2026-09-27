from datetime import datetime

from pydantic import BaseModel, Field


class LocationIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timestamp: datetime


class LocationAccepted(BaseModel):
    accepted: bool = True
    device_id: str
