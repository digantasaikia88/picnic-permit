"""permit approval and verification code

Revision ID: 6ff35067637c
Revises: 3ee6e972ac4b
Create Date: 2026-11-20 08:24:24.750747+05:30
"""

from collections.abc import Sequence

import secrets

import sqlalchemy as sa
from alembic import op


revision: str = '6ff35067637c'
down_revision: str | Sequence[str] | None = '3ee6e972ac4b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Letters and digits that are not mistaken for one another when read aloud or typed.
CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def upgrade() -> None:
    op.add_column('applications', sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('applications', sa.Column('approved_by', sa.String(length=220), nullable=True))
    op.add_column('applications', sa.Column('verify_code', sa.String(length=16), nullable=True))
    op.create_unique_constraint(op.f('uq_applications_verify_code'), 'applications', ['verify_code'])

    # Applications approved before permits existed get a verification code now,
    # and the approval details from the change log.
    connection = op.get_bind()
    approved = connection.execute(
        sa.text("SELECT id FROM applications WHERE status = 'APPROVED' ORDER BY id")
    ).scalars().all()
    for application_id in approved:
        log = connection.execute(
            sa.text(
                "SELECT at, officer_name, officer_designation FROM audit_log "
                "WHERE entity_type = 'application' AND entity_id = :id "
                "AND action = 'application.approved' ORDER BY id DESC LIMIT 1"
            ),
            {"id": str(application_id)},
        ).first()
        by = None
        if log is not None and log.officer_name:
            by = f"{log.officer_name}, {log.officer_designation}"
        connection.execute(
            sa.text(
                "UPDATE applications SET verify_code = :code, approved_by = :by, "
                "approved_at = COALESCE(:at, updated_at) WHERE id = :id"
            ),
            {
                "code": "".join(secrets.choice(CODE_ALPHABET) for _ in range(10)),
                "by": by,
                "at": log.at if log is not None else None,
                "id": application_id,
            },
        )


def downgrade() -> None:
    op.drop_constraint(op.f('uq_applications_verify_code'), 'applications', type_='unique')
    op.drop_column('applications', 'verify_code')
    op.drop_column('applications', 'approved_by')
    op.drop_column('applications', 'approved_at')
