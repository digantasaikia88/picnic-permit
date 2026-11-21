"""status access correction and emergency contacts

Revision ID: fdbcd89a14b3
Revises: 842dfdfa8525
Create Date: 2026-11-19 23:07:00.375782+05:30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'fdbcd89a14b3'
down_revision: str | Sequence[str] | None = '842dfdfa8525'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('applicant_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('mobile', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_applicant_sessions')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_applicant_sessions_token_hash'))
    )
    op.create_index(op.f('ix_applicant_sessions_mobile'), 'applicant_sessions', ['mobile'], unique=False)
    op.create_table('emergency_contacts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('district_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('phone', sa.String(length=40), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['district_id'], ['districts.id'], name=op.f('fk_emergency_contacts_district_id_districts'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_emergency_contacts'))
    )
    op.create_index(op.f('ix_emergency_contacts_district_id'), 'emergency_contacts', ['district_id'], unique=False)
    op.add_column('applications', sa.Column('returned_from_status', sa.Enum('PENDING_DTO', 'ON_HOLD_DUPLICATE_CLAIM', 'PENDING_POLICE', 'PENDING_DC', 'RETURNED_TO_APPLICANT', 'REJECTED', 'APPROVED', 'CANCELLED', 'EXPIRED', name='returned_from_status', native_enum=False, create_constraint=True, length=30), nullable=True))
    op.add_column('applications', sa.Column('status_remarks', sa.Text(), nullable=True))
    op.execute(
        "INSERT INTO app_settings (key, value, min_value, max_value, description) VALUES "
        "('applicant_session_minutes', 30, 5, 240, "
        "'Minutes an applicant stays signed in on the status page after the OTP')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM app_settings WHERE key = 'applicant_session_minutes'")
    op.drop_column('applications', 'status_remarks')
    op.drop_column('applications', 'returned_from_status')
    op.drop_index(op.f('ix_emergency_contacts_district_id'), table_name='emergency_contacts')
    op.drop_table('emergency_contacts')
    op.drop_index(op.f('ix_applicant_sessions_mobile'), table_name='applicant_sessions')
    op.drop_table('applicant_sessions')
