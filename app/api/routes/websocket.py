from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.api.deps import get_connection_manager
from app.core.security import get_current_user_id_ws
from app.services.connection_manager import ConnectionManager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str = Depends(get_current_user_id_ws),
    connection_manager: ConnectionManager = Depends(get_connection_manager),
) -> None:
    """Live map + alert stream.

    One user may hold several concurrent connections (e.g. laptop + phone);
    all of them are registered under the same user_id and receive alerts
    for that user's geozones plus the shared live-map location feed.
    """
    await connection_manager.connect(user_id, websocket)
    try:
        while True:
            # Clients aren't required to send anything; this just lets us
            # detect disconnects promptly instead of leaking dead sockets.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await connection_manager.disconnect(user_id, websocket)
