"""drop filled by centre and leader address

Revision ID: 842dfdfa8525
Revises: 7614ff58f880
Create Date: 2026-11-19 21:37:37.517257+05:30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '842dfdfa8525'
down_revision: str | Sequence[str] | None = '7614ff58f880'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The form no longer asks who filled it, or for the group leader's address.
    op.drop_column('applications', 'centre_name')
    op.drop_column('applications', 'leader_address')
    op.drop_column('applications', 'filled_by')


def downgrade() -> None:
    op.add_column('applications', sa.Column('filled_by', sa.VARCHAR(length=30), server_default='APPLICANT', nullable=False))
    op.add_column('applications', sa.Column('leader_address', sa.TEXT(), server_default='', nullable=False))
    op.add_column('applications', sa.Column('centre_name', sa.VARCHAR(length=150), autoincrement=False, nullable=True))
