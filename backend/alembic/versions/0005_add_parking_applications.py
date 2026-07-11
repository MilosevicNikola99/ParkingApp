"""Add parking applications table.

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-03 15:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


parking_application_status = postgresql.ENUM(
    "pending",
    "selected",
    "cancelled",
    "rejected",
    name="parking_application_status",
    create_type=False,
)


def upgrade() -> None:
    parking_application_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "parking_applications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("availability_id", sa.Integer(), nullable=False),
        sa.Column("applicant_id", sa.Integer(), nullable=False),
        sa.Column("status", parking_application_status, server_default="pending", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["applicant_id"],
            ["users.id"],
            name=op.f("fk_parking_applications_applicant_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["availability_id"],
            ["parking_availabilities.id"],
            name=op.f("fk_parking_applications_availability_id_parking_availabilities"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parking_applications")),
        sa.UniqueConstraint(
            "availability_id",
            "applicant_id",
            name="uq_parking_applications_availability_id_applicant_id",
        ),
    )
    op.create_index(
        "ix_parking_applications_availability_status",
        "parking_applications",
        ["availability_id", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_parking_applications_applicant_id"),
        "parking_applications",
        ["applicant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_parking_applications_availability_id"),
        "parking_applications",
        ["availability_id"],
        unique=False,
    )
    op.create_index(op.f("ix_parking_applications_status"), "parking_applications", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_parking_applications_status"), table_name="parking_applications")
    op.drop_index(op.f("ix_parking_applications_availability_id"), table_name="parking_applications")
    op.drop_index(op.f("ix_parking_applications_applicant_id"), table_name="parking_applications")
    op.drop_index("ix_parking_applications_availability_status", table_name="parking_applications")
    op.drop_table("parking_applications")

    parking_application_status.drop(op.get_bind(), checkfirst=True)
