"""masters users sessions settings audit

Revision ID: eb5a63a36f38
Revises: 
Create Date: 2026-11-19 19:24:06.577835+05:30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'eb5a63a36f38'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    settings_table = op.create_table('app_settings',
    sa.Column('key', sa.String(length=60), nullable=False),
    sa.Column('value', sa.Integer(), nullable=False),
    sa.Column('description', sa.String(length=300), nullable=False),
    sa.Column('min_value', sa.Integer(), nullable=False),
    sa.Column('max_value', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('key', name=op.f('pk_app_settings'))
    )
    op.create_table('captchas',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('answer_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_captchas'))
    )
    op.create_index(op.f('ix_captchas_expires_at'), 'captchas', ['expires_at'], unique=False)
    op.create_table('districts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('short_name', sa.String(length=30), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_districts')),
    sa.UniqueConstraint('code', name=op.f('uq_districts_code')),
    sa.UniqueConstraint('name', name=op.f('uq_districts_name')),
    sa.UniqueConstraint('short_name', name=op.f('uq_districts_short_name'))
    )
    op.create_table('dto_offices',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=30), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('district_id', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['district_id'], ['districts.id'], name=op.f('fk_dto_offices_district_id_districts'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_dto_offices')),
    sa.UniqueConstraint('code', name=op.f('uq_dto_offices_code'))
    )
    op.create_index(op.f('ix_dto_offices_district_id'), 'dto_offices', ['district_id'], unique=False)
    op.create_table('police_stations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('district_id', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['district_id'], ['districts.id'], name=op.f('fk_police_stations_district_id_districts'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_police_stations')),
    sa.UniqueConstraint('district_id', 'name', name=op.f('uq_police_stations_district_id'))
    )
    op.create_index(op.f('ix_police_stations_district_id'), 'police_stations', ['district_id'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.String(length=64), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=True),
    sa.Column('role', sa.Enum('STATE_ADMIN', 'DTO', 'POLICE_STATION', 'DC_OFFICE', 'VIEWER', name='role', native_enum=False, create_constraint=True, length=20), nullable=False),
    sa.Column('office_name', sa.String(length=200), nullable=True),
    sa.Column('district_id', sa.Integer(), nullable=True),
    sa.Column('police_station_id', sa.Integer(), nullable=True),
    sa.Column('dto_office_id', sa.Integer(), nullable=True),
    sa.Column('must_change_password', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('failed_attempts', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('password_issued_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('user_id = lower(user_id)', name=op.f('ck_users_user_id_lowercase')),
    sa.ForeignKeyConstraint(['district_id'], ['districts.id'], name=op.f('fk_users_district_id_districts'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['dto_office_id'], ['dto_offices.id'], name=op.f('fk_users_dto_office_id_dto_offices'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['police_station_id'], ['police_stations.id'], name=op.f('fk_users_police_station_id_police_stations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('user_id', name=op.f('uq_users_user_id'))
    )
    op.create_index(op.f('ix_users_district_id'), 'users', ['district_id'], unique=False)
    op.create_index(op.f('ix_users_dto_office_id'), 'users', ['dto_office_id'], unique=False)
    op.create_index(op.f('ix_users_police_station_id'), 'users', ['police_station_id'], unique=False)
    op.create_table('audit_log',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('actor_user_id', sa.Integer(), nullable=True),
    sa.Column('actor_label', sa.String(length=80), nullable=False),
    sa.Column('action', sa.String(length=60), nullable=False),
    sa.Column('entity_type', sa.String(length=40), nullable=False),
    sa.Column('entity_id', sa.String(length=64), nullable=True),
    sa.Column('entity_label', sa.String(length=200), nullable=True),
    sa.Column('old_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('new_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], name=op.f('fk_audit_log_actor_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_log'))
    )
    op.create_index(op.f('ix_audit_log_action'), 'audit_log', ['action'], unique=False)
    op.create_index(op.f('ix_audit_log_actor_user_id'), 'audit_log', ['actor_user_id'], unique=False)
    op.create_index(op.f('ix_audit_log_at'), 'audit_log', ['at'], unique=False)
    op.create_index(op.f('ix_audit_log_entity_type'), 'audit_log', ['entity_type'], unique=False)
    op.create_table('user_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_sessions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_user_sessions')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_user_sessions_token_hash'))
    )
    op.create_index(op.f('ix_user_sessions_user_id'), 'user_sessions', ['user_id'], unique=False)

    # Audit rows are immutable: the database rejects every change to them.
    op.execute(
        """
        CREATE FUNCTION audit_log_immutable() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log rows cannot be changed or deleted';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_no_update_delete
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION audit_log_immutable()
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_no_truncate
        BEFORE TRUNCATE ON audit_log
        FOR EACH STATEMENT EXECUTE FUNCTION audit_log_immutable()
        """
    )

    # Starting values of the settings (PRD Section 13.4). The admin can change them.
    op.bulk_insert(
        settings_table,
        [
            {"key": "login_max_failed_attempts", "value": 5, "min_value": 3, "max_value": 20,
             "description": "Wrong passwords in a row before an officer account is locked"},
            {"key": "login_lock_minutes", "value": 15, "min_value": 1, "max_value": 1440,
             "description": "Minutes an officer account stays locked"},
            {"key": "password_min_length", "value": 8, "min_value": 8, "max_value": 64,
             "description": "Minimum number of characters in a password"},
            {"key": "generated_password_length", "value": 10, "min_value": 8, "max_value": 32,
             "description": "Number of characters in an auto-generated password"},
            {"key": "session_hours", "value": 48, "min_value": 1, "max_value": 720,
             "description": "Hours an officer stays logged in, with or without activity"},
            {"key": "captcha_valid_minutes", "value": 5, "min_value": 1, "max_value": 30,
             "description": "Minutes a login captcha stays valid"},
        ],
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER audit_log_no_truncate ON audit_log")
    op.execute("DROP TRIGGER audit_log_no_update_delete ON audit_log")
    op.execute("DROP FUNCTION audit_log_immutable()")
    op.drop_index(op.f('ix_user_sessions_user_id'), table_name='user_sessions')
    op.drop_table('user_sessions')
    op.drop_index(op.f('ix_audit_log_entity_type'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_at'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_actor_user_id'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_action'), table_name='audit_log')
    op.drop_table('audit_log')
    op.drop_index(op.f('ix_users_police_station_id'), table_name='users')
    op.drop_index(op.f('ix_users_dto_office_id'), table_name='users')
    op.drop_index(op.f('ix_users_district_id'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_police_stations_district_id'), table_name='police_stations')
    op.drop_table('police_stations')
    op.drop_index(op.f('ix_dto_offices_district_id'), table_name='dto_offices')
    op.drop_table('dto_offices')
    op.drop_table('districts')
    op.drop_index(op.f('ix_captchas_expires_at'), table_name='captchas')
    op.drop_table('captchas')
    op.drop_table('app_settings')
