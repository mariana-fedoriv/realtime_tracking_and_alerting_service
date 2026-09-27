import asyncio
import logging

from redis.asyncio import Redis
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, Location
from app.schemas.device import LocationIn
from app.schemas.ws import AlertEvent, LocationUpdateEvent, WsOutboundEvent
from app.services.geozone_service import find_matching_geozones
from app.services.redis_bus import publish_event
from app.services.spatial import geography_point

logger = logging.getLogger(__name__)


async def process_location(
    session_factory: async_sessionmaker, redis: Redis, payload: LocationIn
) -> None:
    """Persist one location report and evaluate it against every geozone.

    Runs inside a queue-drained background worker (see ingestion_worker
    below), decoupled from the HTTP request/response cycle so a burst of
    ingestion traffic cannot block request handling or exhaust the DB pool.
    """
    async with session_factory() as session:
        upsert_device = (
            pg_insert(Device)
            .values(device_id=payload.device_id)
            .on_conflict_do_nothing(index_elements=[Device.device_id])
        )
        await session.execute(upsert_device)

        session.add(
            Location(
                device_id=payload.device_id,
                point=geography_point(payload.latitude, payload.longitude),
                recorded_at=payload.timestamp,
            )
        )

        matches = await find_matching_geozones(session, payload.latitude, payload.longitude)
        await session.commit()

    await publish_event(
        redis,
        WsOutboundEvent(
            target_user_id=None,
            event=LocationUpdateEvent(
                device_id=payload.device_id,
                latitude=payload.latitude,
                longitude=payload.longitude,
                timestamp=payload.timestamp,
            ),
        ),
    )

    for geozone, owner_user_id in matches:
        await publish_event(
            redis,
            WsOutboundEvent(
                target_user_id=owner_user_id,
                event=AlertEvent(
                    geozone_id=geozone.id,
                    geozone_name=geozone.name,
                    device_id=payload.device_id,
                    latitude=payload.latitude,
                    longitude=payload.longitude,
                    timestamp=payload.timestamp,
                ),
            ),
        )


async def ingestion_worker(
    queue: "asyncio.Queue[LocationIn]",
    session_factory: async_sessionmaker,
    redis: Redis,
) -> None:
    """Long-running consumer: one of `ingest_worker_count` fan-out workers.

    Draining a bounded asyncio.Queue with a fixed worker pool caps the
    number of concurrent DB operations independent of inbound HTTP
    concurrency, which is what keeps the connection pool from being
    exhausted when thousands of devices report at once.
    """
    while True:
        payload = await queue.get()
        try:
            await process_location(session_factory, redis, payload)
        except Exception:
            logger.exception("Failed to process location for device %s", payload.device_id)
        finally:
            queue.task_done()
