from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class LocationUpdateEvent(BaseModel):
    type: Literal["location_update"] = "location_update"
    device_id: str
    latitude: float
    longitude: float
    timestamp: datetime


class AlertEvent(BaseModel):
    type: Literal["alert"] = "alert"
    geozone_id: int
    geozone_name: str
    device_id: str
    latitude: float
    longitude: float
    timestamp: datetime


class WsOutboundEvent(BaseModel):
    """Envelope published on the Redis bus and fanned out to matching WS clients."""

    target_user_id: str | None = None
    """None means broadcast to every connected client (live map); otherwise the alert
    is routed only to the owning user's active sessions."""
    event: LocationUpdateEvent | AlertEvent
