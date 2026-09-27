import pytest

from app.schemas.geozone import GeozoneCreate, GeozoneUpdate
from app.services import geozone_service

USER_A = "user-a"
USER_B = "user-b"

# San Francisco Ferry Building, roughly.
CENTER_LAT, CENTER_LON = 37.7955, -122.3937


async def test_create_and_get_geozone_round_trips_coordinates(session):
    created = await geozone_service.create_geozone(
        session, USER_A, GeozoneCreate(name="Ferry Building", latitude=CENTER_LAT, longitude=CENTER_LON, radius_m=300)
    )
    fetched = await geozone_service.get_geozone(session, USER_A, created.id)
    assert fetched is not None
    assert fetched.name == "Ferry Building"
    assert fetched.latitude == pytest.approx(CENTER_LAT)
    assert fetched.longitude == pytest.approx(CENTER_LON)
    assert fetched.radius_m == 300


async def test_geozones_are_isolated_per_user(session):
    await geozone_service.create_geozone(
        session, USER_A, GeozoneCreate(name="A's zone", latitude=CENTER_LAT, longitude=CENTER_LON, radius_m=300)
    )
    zones_for_b = await geozone_service.list_geozones(session, USER_B)
    assert zones_for_b == []


async def test_find_matching_geozones_uses_st_dwithin_radius(session):
    zone = await geozone_service.create_geozone(
        session, USER_A, GeozoneCreate(name="Small zone", latitude=CENTER_LAT, longitude=CENTER_LON, radius_m=200)
    )

    # ~50m away: inside the 200m radius.
    nearby_matches = await geozone_service.find_matching_geozones(session, CENTER_LAT + 0.0004, CENTER_LON)
    assert any(z.id == zone.id for z, _ in nearby_matches)

    # ~5km away: well outside the 200m radius.
    far_matches = await geozone_service.find_matching_geozones(session, CENTER_LAT + 0.05, CENTER_LON)
    assert all(z.id != zone.id for z, _ in far_matches)


async def test_update_geozone_moves_center_and_resizes(session):
    zone = await geozone_service.create_geozone(
        session, USER_A, GeozoneCreate(name="Movable", latitude=CENTER_LAT, longitude=CENTER_LON, radius_m=100)
    )
    updated = await geozone_service.update_geozone(
        session, USER_A, zone.id, GeozoneUpdate(radius_m=1000)
    )
    assert updated.radius_m == 1000
    assert updated.latitude == pytest.approx(CENTER_LAT)


async def test_delete_geozone_removes_it(session):
    zone = await geozone_service.create_geozone(
        session, USER_A, GeozoneCreate(name="Temp", latitude=CENTER_LAT, longitude=CENTER_LON, radius_m=100)
    )
    deleted = await geozone_service.delete_geozone(session, USER_A, zone.id)
    assert deleted is True
    assert await geozone_service.get_geozone(session, USER_A, zone.id) is None
