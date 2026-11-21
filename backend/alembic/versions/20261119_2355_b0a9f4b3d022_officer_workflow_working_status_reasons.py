"""officer workflow working status reasons

Revision ID: b0a9f4b3d022
Revises: fdbcd89a14b3
Create Date: 2026-11-19 23:55:50.555740+05:30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'b0a9f4b3d022'
down_revision: str | Sequence[str] | None = 'fdbcd89a14b3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


WORKING_STATUSES = [
    "Document verification in progress",
    "Awaiting documents from applicant",
    "Inspection scheduled",
    "Inspection completed",
    "Verification in progress",
    "Field verification scheduled",
    "Under review",
    "Put up for approval",
]

RETURN_REASONS = [
    "Document not readable",
    "Document missing",
    "Document expired or not valid on the travel date",
    "Details do not match the documents",
    "Vehicle not brought for inspection",
    "Destination or route details unclear",
    "Passenger details incomplete",
    "Other",
]

REJECT_REASONS = [
    "Vehicle not eligible (goods vehicle, truck, tractor or trailer)",
    "Vehicle documents not valid",
    "Unpaid traffic challans",
    "Driver's licence not valid or under suspension",
    "Driver has a disqualifying conviction",
    "Vehicle failed inspection",
    "Destination beyond 90 minutes",
    "Safety or law-and-order concern",
    "Not authorised by the vehicle owner or driver",
    "False information",
    "Other",
]


def upgrade() -> None:
    op.create_table('remark_reasons',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=10), nullable=False),
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_remark_reasons')),
    sa.UniqueConstraint('kind', 'name', name=op.f('uq_remark_reasons_kind'))
    )
    op.create_table('working_statuses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_working_statuses')),
    sa.UniqueConstraint('name', name=op.f('uq_working_statuses_name'))
    )
    op.add_column('applications', sa.Column('working_status_id', sa.Integer(), nullable=True))
    op.create_foreign_key(op.f('fk_applications_working_status_id_working_statuses'), 'applications', 'working_statuses', ['working_status_id'], ['id'], ondelete='RESTRICT')
    op.add_column('audit_log', sa.Column('officer_name', sa.String(length=100), nullable=True))
    op.add_column('audit_log', sa.Column('officer_designation', sa.String(length=100), nullable=True))

    # Starting lists (PRD Section 13.4). The admin can add to them or edit them.
    # "Received" is not a row: it is what an application shows until an office sets a status.
    op.bulk_insert(
        sa.table("working_statuses", sa.column("name", sa.String)),
        [{"name": name} for name in WORKING_STATUSES],
    )
    op.bulk_insert(
        sa.table("remark_reasons", sa.column("kind", sa.String), sa.column("name", sa.String)),
        [{"kind": "RETURN", "name": name} for name in RETURN_REASONS]
        + [{"kind": "REJECT", "name": name} for name in REJECT_REASONS],
    )


def downgrade() -> None:
    op.drop_column('audit_log', 'officer_designation')
    op.drop_column('audit_log', 'officer_name')
    op.drop_constraint(op.f('fk_applications_working_status_id_working_statuses'), 'applications', type_='foreignkey')
    op.drop_column('applications', 'working_status_id')
    op.drop_table('working_statuses')
    op.drop_table('remark_reasons')
