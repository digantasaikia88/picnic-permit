"""applications otp sms uploads season

Revision ID: 7614ff58f880
Revises: eb5a63a36f38
Create Date: 2026-11-19 20:01:22.243079+05:30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '7614ff58f880'
down_revision: str | Sequence[str] | None = 'eb5a63a36f38'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_SETTINGS = [
    ("min_days_before_travel", 7, 0, 60,
     "Earliest travel date: days after the date of submission"),
    ("max_days_before_travel", 90, 7, 365,
     "Latest travel date: days after the date of submission"),
    ("earliest_departure_hour", 7, 0, 22,
     "Earliest departure, hour of the day (7 means 7:00 AM)"),
    ("latest_return_hour", 18, 1, 23, "Latest return, hour of the day (18 means 6:00 PM)"),
    ("leader_min_age", 18, 0, 100, "Minimum age of the group leader, in years"),
    ("child_free_below_age", 0, 0, 18,
     "Children younger than this age do not count towards the seats (0 means everyone counts)"),
    ("upload_max_mb", 5, 1, 20, "Largest size of an uploaded file, in MB"),
    ("temp_upload_hours", 24, 1, 168,
     "Hours an uploaded file is kept if the form is not submitted"),
    ("otp_length", 6, 4, 8, "Number of digits in an OTP"),
    ("otp_valid_minutes", 5, 1, 30, "Minutes an OTP stays valid"),
    ("otp_max_attempts", 3, 1, 10, "Wrong attempts allowed on one OTP"),
    ("otp_resend_seconds", 60, 10, 600, "Seconds to wait before another OTP can be sent"),
    ("otp_max_per_hour", 5, 1, 30, "OTPs that can be sent to one mobile number in 1 hour"),
    ("applications_per_mobile_per_day", 3, 1, 50,
     "Applications one mobile number can submit in a day"),
]


def upgrade() -> None:
    op.create_table('application_sequences',
    sa.Column('year', sa.Integer(), nullable=False),
    sa.Column('district_code', sa.Integer(), nullable=False),
    sa.Column('last_serial', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('year', 'district_code', name=op.f('pk_application_sequences'))
    )
    op.create_table('otp_challenges',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('mobile', sa.String(length=10), nullable=False),
    sa.Column('purpose', sa.String(length=40), nullable=False),
    sa.Column('code_hash', sa.String(length=64), nullable=False),
    sa.Column('attempts', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_otp_challenges'))
    )
    op.create_index(op.f('ix_otp_challenges_created_at'), 'otp_challenges', ['created_at'], unique=False)
    op.create_index(op.f('ix_otp_challenges_mobile'), 'otp_challenges', ['mobile'], unique=False)
    op.create_table('picnic_season',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_picnic_season'))
    )
    op.create_table('rate_limit_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('bucket', sa.String(length=120), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rate_limit_events'))
    )
    op.create_index('ix_rate_limit_events_bucket_at', 'rate_limit_events', ['bucket', 'at'], unique=False)
    op.create_table('temp_uploads',
    sa.Column('token', sa.String(length=36), nullable=False),
    sa.Column('doc_type', sa.Enum('RC', 'INSURANCE', 'PUC', 'ROAD_TAX', 'VEHICLE_PERMIT', 'SLD_CERTIFICATE', 'INSPECTION_CERTIFICATE', 'OWNER_SELF_CERTIFICATE', 'DRIVING_LICENCE', name='doc_type', native_enum=False, create_constraint=True, length=30), nullable=False),
    sa.Column('stored_name', sa.String(length=80), nullable=False),
    sa.Column('original_name', sa.String(length=255), nullable=False),
    sa.Column('content_type', sa.String(length=50), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('token', name=op.f('pk_temp_uploads')),
    sa.UniqueConstraint('stored_name', name=op.f('uq_temp_uploads_stored_name'))
    )
    op.create_index(op.f('ix_temp_uploads_expires_at'), 'temp_uploads', ['expires_at'], unique=False)
    op.create_table('vehicle_types',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_vehicle_types')),
    sa.UniqueConstraint('name', name=op.f('uq_vehicle_types_name'))
    )
    op.create_table('applications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('application_number', sa.String(length=11), nullable=False),
    sa.Column('status', sa.Enum('PENDING_DTO', 'ON_HOLD_DUPLICATE_CLAIM', 'PENDING_POLICE', 'PENDING_DC', 'RETURNED_TO_APPLICANT', 'REJECTED', 'APPROVED', 'CANCELLED', 'EXPIRED', name='status', native_enum=False, create_constraint=True, length=30), nullable=False),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('submission_date', sa.Date(), nullable=False),
    sa.Column('filled_by', sa.Enum('APPLICANT', 'CENTRE', name='filled_by', native_enum=False, create_constraint=True, length=30), nullable=False),
    sa.Column('centre_name', sa.String(length=150), nullable=True),
    sa.Column('leader_name', sa.String(length=100), nullable=False),
    sa.Column('leader_age', sa.Integer(), nullable=False),
    sa.Column('leader_gender', sa.Enum('MALE', 'FEMALE', 'OTHER', name='leader_gender', native_enum=False, create_constraint=True, length=30), nullable=False),
    sa.Column('leader_mobile', sa.String(length=10), nullable=False),
    sa.Column('leader_address', sa.Text(), nullable=False),
    sa.Column('travel_date', sa.Date(), nullable=False),
    sa.Column('departure_time', sa.Time(), nullable=False),
    sa.Column('return_time', sa.Time(), nullable=False),
    sa.Column('origin_address', sa.Text(), nullable=False),
    sa.Column('origin_district_id', sa.Integer(), nullable=False),
    sa.Column('origin_police_station_id', sa.Integer(), nullable=False),
    sa.Column('dto_office_id', sa.Integer(), nullable=False),
    sa.Column('destination_address', sa.Text(), nullable=False),
    sa.Column('destination_district_id', sa.Integer(), nullable=False),
    sa.Column('destination_police_station_id', sa.Integer(), nullable=True),
    sa.Column('driving_band', sa.Enum('UP_TO_60', 'FROM_60_TO_90', name='driving_band', native_enum=False, create_constraint=True, length=30), nullable=False),
    sa.Column('needs_dc_specific_approval', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('vehicle_reg_number', sa.String(length=20), nullable=False),
    sa.Column('vehicle_reg_key', sa.String(length=20), nullable=False),
    sa.Column('vehicle_type_id', sa.Integer(), nullable=False),
    sa.Column('vehicle_usage', sa.Enum('PRIVATE', 'HIRED', name='vehicle_usage', native_enum=False, create_constraint=True, length=30), nullable=False),
    sa.Column('seating_capacity', sa.Integer(), nullable=False),
    sa.Column('owner_name', sa.String(length=100), nullable=False),
    sa.Column('owner_mobile', sa.String(length=10), nullable=False),
    sa.Column('inspection_status', sa.Enum('CERTIFICATE_UPLOADED', 'INSPECTION_REQUIRED', 'INSPECTION_SCHEDULED', 'PASSED', 'FAILED', name='inspection_status', native_enum=False, create_constraint=True, length=30), nullable=False),
    sa.Column('driver_name', sa.String(length=100), nullable=False),
    sa.Column('licence_number', sa.String(length=25), nullable=False),
    sa.Column('licence_key', sa.String(length=25), nullable=False),
    sa.Column('licence_class', sa.String(length=60), nullable=False),
    sa.Column('licence_valid_until', sa.Date(), nullable=False),
    sa.Column('driver_mobile', sa.String(length=10), nullable=False),
    sa.Column('has_handyman', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('handyman_name', sa.String(length=100), nullable=True),
    sa.Column('handyman_mobile', sa.String(length=10), nullable=True),
    sa.Column('declarations', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('total_people', sa.Integer(), nullable=False),
    sa.Column('is_duplicate_claim', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['destination_district_id'], ['districts.id'], name=op.f('fk_applications_destination_district_id_districts'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['destination_police_station_id'], ['police_stations.id'], name=op.f('fk_applications_destination_police_station_id_police_stations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['dto_office_id'], ['dto_offices.id'], name=op.f('fk_applications_dto_office_id_dto_offices'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['origin_district_id'], ['districts.id'], name=op.f('fk_applications_origin_district_id_districts'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['origin_police_station_id'], ['police_stations.id'], name=op.f('fk_applications_origin_police_station_id_police_stations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['vehicle_type_id'], ['vehicle_types.id'], name=op.f('fk_applications_vehicle_type_id_vehicle_types'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_applications')),
    sa.UniqueConstraint('application_number', name=op.f('uq_applications_application_number'))
    )
    op.create_index(op.f('ix_applications_destination_district_id'), 'applications', ['destination_district_id'], unique=False)
    op.create_index(op.f('ix_applications_destination_police_station_id'), 'applications', ['destination_police_station_id'], unique=False)
    op.create_index(op.f('ix_applications_dto_office_id'), 'applications', ['dto_office_id'], unique=False)
    op.create_index(op.f('ix_applications_leader_mobile'), 'applications', ['leader_mobile'], unique=False)
    op.create_index('ix_applications_licence_date', 'applications', ['licence_key', 'travel_date'], unique=False)
    op.create_index(op.f('ix_applications_origin_district_id'), 'applications', ['origin_district_id'], unique=False)
    op.create_index(op.f('ix_applications_origin_police_station_id'), 'applications', ['origin_police_station_id'], unique=False)
    op.create_index(op.f('ix_applications_status'), 'applications', ['status'], unique=False)
    op.create_index(op.f('ix_applications_travel_date'), 'applications', ['travel_date'], unique=False)
    op.create_index('ix_applications_vehicle_date', 'applications', ['vehicle_reg_key', 'travel_date'], unique=False)
    op.create_table('application_documents',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('application_id', sa.Integer(), nullable=False),
    sa.Column('doc_type', sa.Enum('RC', 'INSURANCE', 'PUC', 'ROAD_TAX', 'VEHICLE_PERMIT', 'SLD_CERTIFICATE', 'INSPECTION_CERTIFICATE', 'OWNER_SELF_CERTIFICATE', 'DRIVING_LICENCE', name='doc_type', native_enum=False, create_constraint=True, length=30), nullable=False),
    sa.Column('stored_name', sa.String(length=80), nullable=False),
    sa.Column('original_name', sa.String(length=255), nullable=False),
    sa.Column('content_type', sa.String(length=50), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], name=op.f('fk_application_documents_application_id_applications'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_application_documents')),
    sa.UniqueConstraint('stored_name', name=op.f('uq_application_documents_stored_name'))
    )
    op.create_index(op.f('ix_application_documents_application_id'), 'application_documents', ['application_id'], unique=False)
    op.create_table('application_passengers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('application_id', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('age', sa.Integer(), nullable=False),
    sa.Column('gender', sa.Enum('MALE', 'FEMALE', 'OTHER', name='gender', native_enum=False, create_constraint=True, length=30), nullable=False),
    sa.Column('is_group_leader', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], name=op.f('fk_application_passengers_application_id_applications'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_application_passengers')),
    sa.UniqueConstraint('application_id', 'position', name=op.f('uq_application_passengers_application_id'))
    )
    op.create_index(op.f('ix_application_passengers_application_id'), 'application_passengers', ['application_id'], unique=False)
    op.create_table('sms_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('mobile', sa.String(length=10), nullable=False),
    sa.Column('kind', sa.String(length=40), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('application_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], name=op.f('fk_sms_log_application_id_applications'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sms_log'))
    )
    op.create_index(op.f('ix_sms_log_application_id'), 'sms_log', ['application_id'], unique=False)
    op.create_index(op.f('ix_sms_log_mobile'), 'sms_log', ['mobile'], unique=False)

    # Starting values (PRD Section 13.4). The admin can change all of them.
    op.bulk_insert(
        sa.table("vehicle_types", sa.column("name", sa.String)),
        [
            {"name": "Car / SUV"},
            {"name": "Maxi cab / Traveller"},
            {"name": "Mini bus"},
            {"name": "Bus"},
        ],
    )
    # The season starts with no dates: until the admin sets them, only the
    # minimum and maximum days before travel limit the travel date.
    op.execute("INSERT INTO picnic_season (id, start_date, end_date) VALUES (1, NULL, NULL)")
    op.bulk_insert(
        sa.table(
            "app_settings",
            sa.column("key", sa.String),
            sa.column("value", sa.Integer),
            sa.column("min_value", sa.Integer),
            sa.column("max_value", sa.Integer),
            sa.column("description", sa.String),
        ),
        [
            {"key": key, "value": value, "min_value": low, "max_value": high, "description": text}
            for key, value, low, high, text in NEW_SETTINGS
        ],
    )


def downgrade() -> None:
    keys = ", ".join(f"'{key}'" for key, *_ in NEW_SETTINGS)
    op.execute(f"DELETE FROM app_settings WHERE key IN ({keys})")
    op.drop_index(op.f('ix_sms_log_mobile'), table_name='sms_log')
    op.drop_index(op.f('ix_sms_log_application_id'), table_name='sms_log')
    op.drop_table('sms_log')
    op.drop_index(op.f('ix_application_passengers_application_id'), table_name='application_passengers')
    op.drop_table('application_passengers')
    op.drop_index(op.f('ix_application_documents_application_id'), table_name='application_documents')
    op.drop_table('application_documents')
    op.drop_index('ix_applications_vehicle_date', table_name='applications')
    op.drop_index(op.f('ix_applications_travel_date'), table_name='applications')
    op.drop_index(op.f('ix_applications_status'), table_name='applications')
    op.drop_index(op.f('ix_applications_origin_police_station_id'), table_name='applications')
    op.drop_index(op.f('ix_applications_origin_district_id'), table_name='applications')
    op.drop_index('ix_applications_licence_date', table_name='applications')
    op.drop_index(op.f('ix_applications_leader_mobile'), table_name='applications')
    op.drop_index(op.f('ix_applications_dto_office_id'), table_name='applications')
    op.drop_index(op.f('ix_applications_destination_police_station_id'), table_name='applications')
    op.drop_index(op.f('ix_applications_destination_district_id'), table_name='applications')
    op.drop_table('applications')
    op.drop_table('vehicle_types')
    op.drop_index(op.f('ix_temp_uploads_expires_at'), table_name='temp_uploads')
    op.drop_table('temp_uploads')
    op.drop_index('ix_rate_limit_events_bucket_at', table_name='rate_limit_events')
    op.drop_table('rate_limit_events')
    op.drop_table('picnic_season')
    op.drop_index(op.f('ix_otp_challenges_mobile'), table_name='otp_challenges')
    op.drop_index(op.f('ix_otp_challenges_created_at'), table_name='otp_challenges')
    op.drop_table('otp_challenges')
    op.drop_table('application_sequences')
