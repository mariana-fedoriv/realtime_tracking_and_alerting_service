from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Geozone
from app.schemas.geozone import GeozoneCreate, GeozoneRead, GeozoneUpdate
from app.services.spatial import geography_point


def _to_read(row) -> GeozoneRead:
    geozone, longitude, latitude = row
    return GeozoneRead(
        id=geozone.id,
        name=geozone.name,
        latitude=latitude,
        longitude=longitude,
        radius_m=geozone.radius_m,
        created_at=geozone.created_at,
        updated_at=geozone.updated_at,
    )


def _select_with_coords():
    as_geometry = cast(Geozone.center, Geometry)
    return select(Geozone, func.ST_X(as_geometry), func.ST_Y(as_geometry))


async def create_geozone(
    session: AsyncSession, user_id: str, data: GeozoneCreate
) -> GeozoneRead:
    geozone = Geozone(
        user_id=user_id,
        name=data.name,
        center=geography_point(data.latitude, data.longitude),
        radius_m=data.radius_m,
    )
    session.add(geozone)
    await session.commit()
    await session.refresh(geozone)
    return await get_geozone(session, user_id, geozone.id)


async def list_geozones(session: AsyncSession, user_id: str) -> list[GeozoneRead]:
    stmt = _select_with_coords().where(Geozone.user_id == user_id).order_by(Geozone.id)
    result = await session.execute(stmt)
    return [_to_read(row) for row in result.all()]


async def get_geozone(session: AsyncSession, user_id: str, geozone_id: int) -> GeozoneRead | None:
    stmt = _select_with_coords().where(Geozone.user_id == user_id, Geozone.id == geozone_id)
    result = await session.execute(stmt)
    row = result.first()
    return _to_read(row) if row else None


async def update_geozone(
    session: AsyncSession, user_id: str, geozone_id: int, data: GeozoneUpdate
) -> GeozoneRead | None:
    stmt = select(Geozone).where(Geozone.user_id == user_id, Geozone.id == geozone_id)
    result = await session.execute(stmt)
    geozone = result.scalar_one_or_none()
    if geozone is None:
        return None

    if data.name is not None:
        geozone.name = data.name
    if data.radius_m is not None:
        geozone.radius_m = data.radius_m
    if data.latitude is not None or data.longitude is not None:
        current = await get_geozone(session, user_id, geozone_id)
        latitude = data.latitude if data.latitude is not None else current.latitude
        longitude = data.longitude if data.longitude is not None else current.longitude
        geozone.center = geography_point(latitude, longitude)

    await session.commit()
    return await get_geozone(session, user_id, geozone_id)


async def delete_geozone(session: AsyncSession, user_id: str, geozone_id: int) -> bool:
    stmt = select(Geozone).where(Geozone.user_id == user_id, Geozone.id == geozone_id)
    result = await session.execute(stmt)
    geozone = result.scalar_one_or_none()
    if geozone is None:
        return False
    await session.delete(geozone)
    await session.commit()
    return True


async def find_matching_geozones(
    session: AsyncSession, latitude: float, longitude: float
) -> list[tuple[Geozone, str]]:
    """Return every geozone (across all users) whose radius contains the point.

    Uses ST_DWithin on a geography column so the comparison runs as a single
    indexed spatial query in Postgres/PostGIS rather than pulling rows into
    Python and computing distances by hand.
    """
    point = geography_point(latitude, longitude)
    stmt = select(Geozone).where(func.ST_DWithin(Geozone.center, point, Geozone.radius_m))
    result = await session.execute(stmt)
    zones = result.scalars().all()
    return [(zone, zone.user_id) for zone in zones]
