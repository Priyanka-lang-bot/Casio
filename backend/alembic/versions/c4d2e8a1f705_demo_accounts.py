"""Demo accounts: users.is_demo marks throwaway sandbox accounts created by
the "Try CASIO Demo" button. They hold only generated sample data and are
deleted automatically after a day.

Revision ID: c4d2e8a1f705
Revises: 1bb9a49e4fc5
Create Date: 2026-11-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4d2e8a1f705"
down_revision: Union[str, Sequence[str], None] = "1bb9a49e4fc5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_demo", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.create_index("ix_users_demo_created", "users", ["is_demo", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_users_demo_created", table_name="users")
    op.drop_column("users", "is_demo")
