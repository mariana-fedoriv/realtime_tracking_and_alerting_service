from datetime import datetime

from pydantic import BaseModel, Field


class GeozoneCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_m: float = Field(gt=0, le=100_000)


class GeozoneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    radius_m: float | None = Field(default=None, gt=0, le=100_000)


class GeozoneRead(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    radius_m: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
