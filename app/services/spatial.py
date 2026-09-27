from geoalchemy2 import Geography
from sqlalchemy import cast, func
from sqlalchemy.sql.elements import ColumnElement


def geography_point(latitude: float, longitude: float) -> ColumnElement:
    """Build a WGS84 geography POINT expression from lat/lon for use in queries."""
    return cast(func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326), Geography)
