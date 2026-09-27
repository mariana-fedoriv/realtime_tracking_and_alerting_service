from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import DateTime, Float, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Device(Base):
    """A tracking device identified by an opaque, client-supplied device_id."""

    __tablename__ = "devices"

    device_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    locations: Mapped[list["Location"]] = relationship(
        back_populates="device", cascade="all, delete-orphan"
    )


class Location(Base):
    """A single reported coordinate for a device, stored as a geography point."""

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(
        ForeignKey("devices.device_id", ondelete="CASCADE"), index=True
    )
    point: Mapped[str] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=True)
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    device: Mapped[Device] = relationship(back_populates="locations")

    __table_args__ = (
        Index("ix_locations_device_recorded_at", "device_id", "recorded_at"),
    )


class Geozone(Base):
    """A user-owned circular geofence used to trigger alerts."""

    __tablename__ = "geozones"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(255))
    center: Mapped[str] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=True)
    )
    radius_m: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
