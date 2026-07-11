"""Allow multiple audit events for one reservation.

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-04 15:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_parking_assignment_audit_logs_reservation_id",
        "parking_assignment_audit_logs",
        type_="unique",
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_parking_assignment_audit_logs_reservation_id",
        "parking_assignment_audit_logs",
        ["reservation_id"],
    )
