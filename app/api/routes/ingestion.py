import asyncio

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_ingest_queue
from app.schemas.device import LocationAccepted, LocationIn

router = APIRouter(prefix="/api/v1", tags=["ingestion"])


@router.post(
    "/devices/location",
    response_model=LocationAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_location(
    payload: LocationIn,
    queue: asyncio.Queue = Depends(get_ingest_queue),
) -> LocationAccepted:
    """Accept one device coordinate report for async processing.

    Returns immediately after enqueueing; persistence, geozone evaluation and
    WebSocket fan-out all happen in background workers so this endpoint's
    latency stays flat regardless of downstream load. If the queue is full
    (consumers can't keep up) the client is told to back off with a 503
    rather than piling up unbounded memory.
    """
    try:
        queue.put_nowait(payload)
    except asyncio.QueueFull as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingestion queue is full, retry shortly",
        ) from exc
    return LocationAccepted(device_id=payload.device_id)
