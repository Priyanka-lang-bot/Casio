"""Manual subscriptions: recurring_payments.manual marks payments the user
added by hand (for example a yearly plan not in any statement yet). Automatic
detection never deletes or overwrites them.

Revision ID: d7a3f9b2c610
Revises: c4d2e8a1f705
Create Date: 2026-11-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d7a3f9b2c610"
down_revision: Union[str, Sequence[str], None] = "c4d2e8a1f705"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("recurring_payments", sa.Column("manual", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column("recurring_payments", "manual")
