import pytest
from pydantic import ValidationError

from app.schemas.device import LocationIn
from app.schemas.geozone import GeozoneCreate


def test_location_in_accepts_valid_coordinates():
    location = LocationIn(
        device_id="device-1", latitude=51.5, longitude=-0.12, timestamp="2026-01-01T00:00:00Z"
    )
    assert location.latitude == 51.5


@pytest.mark.parametrize("latitude,longitude", [(91, 0), (-91, 0), (0, 181), (0, -181)])
def test_location_in_rejects_out_of_range_coordinates(latitude, longitude):
    with pytest.raises(ValidationError):
        LocationIn(
            device_id="device-1",
            latitude=latitude,
            longitude=longitude,
            timestamp="2026-01-01T00:00:00Z",
        )


def test_geozone_create_rejects_non_positive_radius():
    with pytest.raises(ValidationError):
        GeozoneCreate(name="zone", latitude=0, longitude=0, radius_m=0)


def test_geozone_create_accepts_valid_payload():
    geozone = GeozoneCreate(name="zone", latitude=10, longitude=20, radius_m=500)
    assert geozone.radius_m == 500
