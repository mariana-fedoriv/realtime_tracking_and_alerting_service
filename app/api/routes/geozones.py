from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.security import get_current_user_id
from app.schemas.geozone import GeozoneCreate, GeozoneRead, GeozoneUpdate
from app.services import geozone_service

router = APIRouter(prefix="/api/v1/geozones", tags=["geozones"])


@router.post("", response_model=GeozoneRead, status_code=status.HTTP_201_CREATED)
async def create_geozone(
    data: GeozoneCreate,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> GeozoneRead:
    return await geozone_service.create_geozone(session, user_id, data)


@router.get("", response_model=list[GeozoneRead])
async def list_geozones(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[GeozoneRead]:
    return await geozone_service.list_geozones(session, user_id)


@router.get("/{geozone_id}", response_model=GeozoneRead)
async def get_geozone(
    geozone_id: int,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> GeozoneRead:
    geozone = await geozone_service.get_geozone(session, user_id, geozone_id)
    if geozone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Geozone not found")
    return geozone


@router.put("/{geozone_id}", response_model=GeozoneRead)
async def update_geozone(
    geozone_id: int,
    data: GeozoneUpdate,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> GeozoneRead:
    geozone = await geozone_service.update_geozone(session, user_id, geozone_id, data)
    if geozone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Geozone not found")
    return geozone


@router.delete("/{geozone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_geozone(
    geozone_id: int,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    deleted = await geozone_service.delete_geozone(session, user_id, geozone_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Geozone not found")
