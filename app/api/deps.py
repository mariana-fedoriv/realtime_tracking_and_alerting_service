import asyncio

from fastapi import Request
from redis.asyncio import Redis
from starlette.requests import HTTPConnection

from app.db.session import get_session
from app.services.connection_manager import ConnectionManager

__all__ = ["get_session", "get_ingest_queue", "get_redis", "get_connection_manager"]


def get_ingest_queue(request: Request) -> "asyncio.Queue":
    return request.app.state.ingest_queue


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


def get_connection_manager(conn: HTTPConnection) -> ConnectionManager:
    """HTTPConnection is the common base of Request and WebSocket, so this
    dependency resolves in both regular HTTP routes and the /ws route."""
    return conn.app.state.connection_manager
