"""Add parking assignment audit logs table.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-04 09:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


parking_assignment_trigger_source = postgresql.ENUM(
    "system",
    "manual_owner",
    "manual_admin",
    "scheduled",
    name="parking_assignment_trigger_source",
    create_type=False,
)


def upgrade() -> None:
    parking_assignment_trigger_source.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "parking_assignment_audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("availability_id", sa.Integer(), nullable=False),
        sa.Column("reservation_id", sa.Integer(), nullable=False),
        sa.Column("selected_application_id", sa.Integer(), nullable=False),
        sa.Column("selected_user_id", sa.Integer(), nullable=False),
        sa.Column("rejected_application_ids", sa.JSON(), nullable=False),
        sa.Column("ranking_policy", sa.String(length=100), nullable=False),
        sa.Column("ranking_details", sa.JSON(), nullable=False),
        sa.Column(
            "trigger_source",
            parking_assignment_trigger_source,
            server_default="system",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["availability_id"],
            ["parking_availabilities.id"],
            name=op.f("fk_parking_assignment_audit_logs_availability_id_parking_availabilities"),
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id"],
            ["parking_reservations.id"],
            name=op.f("fk_parking_assignment_audit_logs_reservation_id_parking_reservations"),
        ),
        sa.ForeignKeyConstraint(
            ["selected_application_id"],
            ["parking_applications.id"],
            name=op.f("fk_parking_assignment_audit_logs_selected_application_id_parking_applications"),
        ),
        sa.ForeignKeyConstraint(
            ["selected_user_id"],
            ["users.id"],
            name=op.f("fk_parking_assignment_audit_logs_selected_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parking_assignment_audit_logs")),
        sa.UniqueConstraint("reservation_id", name="uq_parking_assignment_audit_logs_reservation_id"),
    )
    op.create_index(
        op.f("ix_parking_assignment_audit_logs_availability_id"),
        "parking_assignment_audit_logs",
        ["availability_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_parking_assignment_audit_logs_created_at"),
        "parking_assignment_audit_logs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_parking_assignment_audit_logs_reservation_id"),
        "parking_assignment_audit_logs",
        ["reservation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_parking_assignment_audit_logs_selected_application_id"),
        "parking_assignment_audit_logs",
        ["selected_application_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_parking_assignment_audit_logs_selected_user_id"),
        "parking_assignment_audit_logs",
        ["selected_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_parking_assignment_audit_logs_selected_user_id"), table_name="parking_assignment_audit_logs")
    op.drop_index(
        op.f("ix_parking_assignment_audit_logs_selected_application_id"),
        table_name="parking_assignment_audit_logs",
    )
    op.drop_index(op.f("ix_parking_assignment_audit_logs_reservation_id"), table_name="parking_assignment_audit_logs")
    op.drop_index(op.f("ix_parking_assignment_audit_logs_created_at"), table_name="parking_assignment_audit_logs")
    op.drop_index(op.f("ix_parking_assignment_audit_logs_availability_id"), table_name="parking_assignment_audit_logs")
    op.drop_table("parking_assignment_audit_logs")

    parking_assignment_trigger_source.drop(op.get_bind(), checkfirst=True)
