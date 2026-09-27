import asyncio
import contextlib
import logging

from redis.asyncio import Redis

from app.config import get_settings
from app.schemas.ws import WsOutboundEvent
from app.services.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)
settings = get_settings()


async def publish_event(redis: Redis, event: WsOutboundEvent) -> None:
    await redis.publish(settings.redis_ws_channel, event.model_dump_json())


async def redis_listener(redis: Redis, connection_manager: ConnectionManager) -> None:
    """Background task: one per app replica.

    Every replica publishes every event to the shared channel and every
    replica subscribes to it. Each replica only delivers to WebSocket
    connections it physically holds, so a user connected to replica A gets
    alerts even if the triggering device data was ingested by replica B.
    """
    pubsub = redis.pubsub()
    await pubsub.subscribe(settings.redis_ws_channel)
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                event = WsOutboundEvent.model_validate_json(message["data"])
            except ValueError:
                logger.warning("Discarding malformed ws event from redis bus")
                continue

            payload = event.event.model_dump_json()
            if event.target_user_id is None:
                await connection_manager.broadcast(payload)
            else:
                await connection_manager.send_to_user(event.target_user_id, payload)
    except asyncio.CancelledError:
        pass
    finally:
        with contextlib.suppress(Exception):
            await pubsub.unsubscribe(settings.redis_ws_channel)
            await pubsub.aclose()
