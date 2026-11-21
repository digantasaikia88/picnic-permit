"""officer workflow part b findings inspection flags

Revision ID: 22e49fe153d8
Revises: b0a9f4b3d022
Create Date: 2026-11-20 00:30:52.878167+05:30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '22e49fe153d8'
down_revision: str | Sequence[str] | None = 'b0a9f4b3d022'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('flagged_mobiles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('mobile', sa.String(length=10), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('application_number', sa.String(length=11), nullable=True),
    sa.Column('flagged_by', sa.String(length=160), nullable=False),
    sa.Column('is_blocked', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_flagged_mobiles')),
    sa.UniqueConstraint('mobile', name=op.f('uq_flagged_mobiles_mobile'))
    )
    op.add_column('application_documents', sa.Column('verified', sa.Boolean(), nullable=True))
    op.add_column('applications', sa.Column('dto_findings', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('applications', sa.Column('inspection', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('applications', sa.Column('certificate_confirmed_doc_id', sa.Integer(), nullable=True))
    op.add_column('applications', sa.Column('police_findings', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('applications', sa.Column('dc_specific_approval_remark', sa.Text(), nullable=True))
    op.create_foreign_key('fk_applications_confirmed_certificate', 'applications', 'application_documents', ['certificate_confirmed_doc_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_applications_confirmed_certificate', 'applications', type_='foreignkey')
    op.drop_column('applications', 'dc_specific_approval_remark')
    op.drop_column('applications', 'police_findings')
    op.drop_column('applications', 'certificate_confirmed_doc_id')
    op.drop_column('applications', 'inspection')
    op.drop_column('applications', 'dto_findings')
    op.drop_column('application_documents', 'verified')
    op.drop_table('flagged_mobiles')
