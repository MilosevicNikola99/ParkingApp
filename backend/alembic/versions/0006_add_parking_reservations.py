"""Add parking reservations table.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-03 16:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


parking_reservation_status = postgresql.ENUM(
    "active",
    "cancelled",
    "completed",
    name="parking_reservation_status",
    create_type=False,
)


def upgrade() -> None:
    parking_reservation_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "parking_reservations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("availability_id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=True),
        sa.Column("parking_spot_id", sa.Integer(), nullable=False),
        sa.Column("reserved_for_user_id", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", parking_reservation_status, server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["parking_applications.id"],
            name=op.f("fk_parking_reservations_application_id_parking_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["availability_id"],
            ["parking_availabilities.id"],
            name=op.f("fk_parking_reservations_availability_id_parking_availabilities"),
        ),
        sa.ForeignKeyConstraint(
            ["parking_spot_id"],
            ["parking_spots.id"],
            name=op.f("fk_parking_reservations_parking_spot_id_parking_spots"),
        ),
        sa.ForeignKeyConstraint(
            ["reserved_for_user_id"],
            ["users.id"],
            name=op.f("fk_parking_reservations_reserved_for_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parking_reservations")),
        sa.UniqueConstraint("application_id", name="uq_parking_reservations_application_id"),
        sa.UniqueConstraint("availability_id", name="uq_parking_reservations_availability_id"),
    )
    op.create_index(
        op.f("ix_parking_reservations_application_id"),
        "parking_reservations",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_parking_reservations_availability_id"),
        "parking_reservations",
        ["availability_id"],
        unique=False,
    )
    op.create_index(op.f("ix_parking_reservations_end_at"), "parking_reservations", ["end_at"], unique=False)
    op.create_index(
        op.f("ix_parking_reservations_parking_spot_id"),
        "parking_reservations",
        ["parking_spot_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_parking_reservations_reserved_for_user_id"),
        "parking_reservations",
        ["reserved_for_user_id"],
        unique=False,
    )
    op.create_index(op.f("ix_parking_reservations_start_at"), "parking_reservations", ["start_at"], unique=False)
    op.create_index(op.f("ix_parking_reservations_status"), "parking_reservations", ["status"], unique=False)
    op.create_index(
        "ix_parking_reservations_spot_start_end",
        "parking_reservations",
        ["parking_spot_id", "start_at", "end_at"],
        unique=False,
    )
    op.create_index(
        "ix_parking_reservations_user_status",
        "parking_reservations",
        ["reserved_for_user_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_parking_reservations_user_status", table_name="parking_reservations")
    op.drop_index("ix_parking_reservations_spot_start_end", table_name="parking_reservations")
    op.drop_index(op.f("ix_parking_reservations_status"), table_name="parking_reservations")
    op.drop_index(op.f("ix_parking_reservations_start_at"), table_name="parking_reservations")
    op.drop_index(op.f("ix_parking_reservations_reserved_for_user_id"), table_name="parking_reservations")
    op.drop_index(op.f("ix_parking_reservations_parking_spot_id"), table_name="parking_reservations")
    op.drop_index(op.f("ix_parking_reservations_end_at"), table_name="parking_reservations")
    op.drop_index(op.f("ix_parking_reservations_availability_id"), table_name="parking_reservations")
    op.drop_index(op.f("ix_parking_reservations_application_id"), table_name="parking_reservations")
    op.drop_table("parking_reservations")

    parking_reservation_status.drop(op.get_bind(), checkfirst=True)
