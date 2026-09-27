import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from redis.asyncio import Redis

from app.api.routes import geozones, ingestion, websocket
from app.config import get_settings
from app.db.session import async_session_factory, engine
from app.schemas.device import LocationIn
from app.services.connection_manager import ConnectionManager
from app.services.ingestion_service import ingestion_worker
from app.services.redis_bus import redis_listener

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app.state.connection_manager = ConnectionManager()
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    app.state.ingest_queue: asyncio.Queue[LocationIn] = asyncio.Queue(
        maxsize=settings.ingest_queue_maxsize
    )

    background_tasks = [
        asyncio.create_task(
            ingestion_worker(app.state.ingest_queue, async_session_factory, app.state.redis)
        )
        for _ in range(settings.ingest_worker_count)
    ]
    background_tasks.append(
        asyncio.create_task(redis_listener(app.state.redis, app.state.connection_manager))
    )

    try:
        yield
    finally:
        for task in background_tasks:
            task.cancel()
        await asyncio.gather(*background_tasks, return_exceptions=True)
        await app.state.redis.aclose()
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(ingestion.router)
    app.include_router(geozones.router)
    app.include_router(websocket.router)
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
    return app


app = create_app()
