"""Initial migration scaffold.

Revision ID: 0001
Revises:
Create Date: 2026-06-02 21:30:00.000000

This revision is intentionally empty because no business domain models have
been implemented yet. Future model implementation tasks will add the parking
application tables through follow-up migrations.
"""

from collections.abc import Sequence


revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
