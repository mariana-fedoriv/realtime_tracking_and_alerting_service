from fastapi import Header, HTTPException, Query, status

USER_ID_HEADER = "X-User-Id"


async def get_current_user_id(
    x_user_id: str | None = Header(default=None, alias=USER_ID_HEADER),
) -> str:
    """Mock auth: the caller is trusted to identify themselves via a header.

    Full OAuth is out of scope per the spec; this is enough to demonstrate
    per-user isolation of geozones and multi-session alert routing.
    """
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing required '{USER_ID_HEADER}' header",
        )
    return x_user_id


async def get_current_user_id_ws(
    user_id: str | None = Query(default=None),
) -> str:
    """Same mock auth, but for WebSocket connections where custom headers are
    awkward to set from browser clients, so it is accepted as a query param."""
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing required 'user_id' query param"
        )
    return user_id
