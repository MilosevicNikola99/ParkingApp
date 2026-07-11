"""Add parking spots table.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-03 12:45:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "parking_spots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_parking_spots_owner_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parking_spots")),
    )
    op.create_index(op.f("ix_parking_spots_code"), "parking_spots", ["code"], unique=True)
    op.create_index(op.f("ix_parking_spots_owner_id"), "parking_spots", ["owner_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_parking_spots_owner_id"), table_name="parking_spots")
    op.drop_index(op.f("ix_parking_spots_code"), table_name="parking_spots")
    op.drop_table("parking_spots")
