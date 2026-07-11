"""Add admin override assignment audit trigger.

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-04 13:00:00.000000
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE parking_assignment_trigger_source ADD VALUE IF NOT EXISTS 'admin_override'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely without recreating the type and dependent column.
    pass
