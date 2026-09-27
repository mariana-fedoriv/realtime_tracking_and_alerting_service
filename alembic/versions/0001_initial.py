"""initial schema: postgis extension, devices, locations, geozones

Revision ID: 0001
Revises:
Create Date: 2026-09-10

"""
from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "devices",
        sa.Column("device_id", sa.String(length=128), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )

    op.create_table(
        "locations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "device_id",
            sa.String(length=128),
            sa.ForeignKey("devices.device_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "point",
            geoalchemy2.Geography(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_locations_device_id", "locations", ["device_id"])
    op.create_index(
        "ix_locations_device_recorded_at", "locations", ["device_id", "recorded_at"]
    )
    op.execute(
        "CREATE INDEX ix_locations_point ON locations USING GIST (point)"
    )

    op.create_table(
        "geozones",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "center",
            geoalchemy2.Geography(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("radius_m", sa.Float, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_geozones_user_id", "geozones", ["user_id"])
    op.execute("CREATE INDEX ix_geozones_center ON geozones USING GIST (center)")


def downgrade() -> None:
    op.drop_table("geozones")
    op.drop_index("ix_locations_point", table_name="locations")
    op.drop_index("ix_locations_device_recorded_at", table_name="locations")
    op.drop_index("ix_locations_device_id", table_name="locations")
    op.drop_table("locations")
    op.drop_table("devices")
