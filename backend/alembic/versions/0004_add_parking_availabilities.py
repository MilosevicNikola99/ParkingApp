"""Add parking availabilities table.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-03 13:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


parking_availability_status = postgresql.ENUM(
    "open",
    "assigned",
    "cancelled",
    "expired",
    name="parking_availability_status",
    create_type=False,
)


def upgrade() -> None:
    parking_availability_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "parking_availabilities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("parking_spot_id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", parking_availability_status, server_default="open", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("priority_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_parking_availabilities_owner_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["parking_spot_id"],
            ["parking_spots.id"],
            name=op.f("fk_parking_availabilities_parking_spot_id_parking_spots"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parking_availabilities")),
    )
    op.create_index(
        "ix_parking_availabilities_spot_start_end",
        "parking_availabilities",
        ["parking_spot_id", "start_at", "end_at"],
        unique=False,
    )
    op.create_index(
        "ix_parking_availabilities_status_start_at",
        "parking_availabilities",
        ["status", "start_at"],
        unique=False,
    )
    op.create_index(op.f("ix_parking_availabilities_end_at"), "parking_availabilities", ["end_at"], unique=False)
    op.create_index(op.f("ix_parking_availabilities_owner_id"), "parking_availabilities", ["owner_id"], unique=False)
    op.create_index(
        op.f("ix_parking_availabilities_parking_spot_id"),
        "parking_availabilities",
        ["parking_spot_id"],
        unique=False,
    )
    op.create_index(op.f("ix_parking_availabilities_start_at"), "parking_availabilities", ["start_at"], unique=False)
    op.create_index(op.f("ix_parking_availabilities_status"), "parking_availabilities", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_parking_availabilities_status"), table_name="parking_availabilities")
    op.drop_index(op.f("ix_parking_availabilities_start_at"), table_name="parking_availabilities")
    op.drop_index(op.f("ix_parking_availabilities_parking_spot_id"), table_name="parking_availabilities")
    op.drop_index(op.f("ix_parking_availabilities_owner_id"), table_name="parking_availabilities")
    op.drop_index(op.f("ix_parking_availabilities_end_at"), table_name="parking_availabilities")
    op.drop_index("ix_parking_availabilities_status_start_at", table_name="parking_availabilities")
    op.drop_index("ix_parking_availabilities_spot_start_end", table_name="parking_availabilities")
    op.drop_table("parking_availabilities")

    parking_availability_status.drop(op.get_bind(), checkfirst=True)
