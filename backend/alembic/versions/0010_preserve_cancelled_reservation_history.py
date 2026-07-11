"""Preserve cancelled reservation history and limit active reservations.

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-04 18:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_parking_reservations_availability_id",
        "parking_reservations",
        type_="unique",
    )
    op.create_index(
        "uq_parking_reservations_active_availability_id",
        "parking_reservations",
        ["availability_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_parking_reservations_active_availability_id",
        table_name="parking_reservations",
    )
    op.create_unique_constraint(
        "uq_parking_reservations_availability_id",
        "parking_reservations",
        ["availability_id"],
    )
