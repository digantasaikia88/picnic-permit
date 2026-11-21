"""working status offices

Revision ID: 3ee6e972ac4b
Revises: 22e49fe153d8
Create Date: 2026-11-20 07:11:03.583325+05:30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '3ee6e972ac4b'
down_revision: str | Sequence[str] | None = '22e49fe153d8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Working status: offered to (DTO, police station, DC office)
OFFICES = {
    "Document verification in progress": (True, False, False),
    "Awaiting documents from applicant": (True, False, False),
    "Inspection scheduled": (True, False, False),
    "Inspection completed": (True, False, False),
    "Verification in progress": (False, True, False),
    "Field verification scheduled": (False, True, False),
    "Under review": (False, False, True),
    "Put up for approval": (True, True, True),
}


def upgrade() -> None:
    op.add_column('working_statuses', sa.Column('for_dto', sa.Boolean(), server_default=sa.text('true'), nullable=False))
    op.add_column('working_statuses', sa.Column('for_police', sa.Boolean(), server_default=sa.text('true'), nullable=False))
    op.add_column('working_statuses', sa.Column('for_dc', sa.Boolean(), server_default=sa.text('true'), nullable=False))

    # The offices of the starting list (PRD Section 13.4). A status the admin
    # added, or renamed, stays offered to all three offices until the admin decides.
    table = sa.table(
        "working_statuses",
        sa.column("name", sa.String),
        sa.column("for_dto", sa.Boolean),
        sa.column("for_police", sa.Boolean),
        sa.column("for_dc", sa.Boolean),
    )
    for name, (dto, police, dc) in OFFICES.items():
        op.execute(
            table.update()
            .where(table.c.name == name)
            .values(for_dto=dto, for_police=police, for_dc=dc)
        )


def downgrade() -> None:
    op.drop_column('working_statuses', 'for_dc')
    op.drop_column('working_statuses', 'for_police')
    op.drop_column('working_statuses', 'for_dto')
