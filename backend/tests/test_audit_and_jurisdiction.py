"""The immutable audit log, and jurisdiction rules."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.errors import PermissionDeniedError
from app.models import AuditLog, Role, User
from app.services.jurisdiction import (
    Level,
    jurisdiction_of,
    require_district,
    require_police_station,
)
from tests.conftest import MakeUser, Masters

# ------------------------------------------------------------------ audit log


def test_master_change_writes_who_when_old_and_new(
    admin_client: TestClient, admin: User, m: Masters, db: Session
) -> None:
    admin_client.patch(
        f"/api/admin/districts/{m.tinsukia.id}",
        json={"name": "Tinsukia Sadar", "short_name": "tsk"},
    )

    row = db.scalar(select(AuditLog).where(AuditLog.action == "district.update"))
    assert row.actor_user_id == admin.id
    assert row.actor_label == admin.user_id
    assert row.at is not None
    assert row.old_value == {"name": "Tinsukia", "short_name": "tinsukia"}
    assert row.new_value == {"name": "Tinsukia Sadar", "short_name": "tsk"}


def test_no_audit_row_when_nothing_changed(
    admin_client: TestClient, m: Masters, db: Session
) -> None:
    admin_client.patch(f"/api/admin/districts/{m.tinsukia.id}", json={"name": "Tinsukia"})
    assert db.scalar(select(AuditLog).where(AuditLog.action == "district.update")) is None


def test_audit_rows_cannot_be_updated_deleted_or_truncated(db: Session, m: Masters) -> None:
    row_id = db.scalar(select(AuditLog.id).limit(1))
    assert row_id is not None

    for statement in (
        update(AuditLog).where(AuditLog.id == row_id).values(action="tampered"),
        delete(AuditLog).where(AuditLog.id == row_id),
        text("TRUNCATE audit_log"),
    ):
        with pytest.raises(DBAPIError, match="cannot be changed or deleted"), db.begin_nested():
            db.execute(statement)

    assert db.scalar(select(AuditLog.action).where(AuditLog.id == row_id)) != "tampered"


def test_admin_can_read_the_audit_log_newest_first(admin_client: TestClient, m: Masters) -> None:
    admin_client.post(
        "/api/admin/police-stations", json={"name": "Makum PS", "district_id": m.tinsukia.id}
    )
    body = admin_client.get("/api/admin/audit-log", params={"page_size": 5}).json()
    assert body["items"][0]["action"] == "police_station.create"
    assert body["items"][0]["entity_label"] == "Makum PS"
    assert body["total"] > 5

    filtered = admin_client.get("/api/admin/audit-log", params={"entity_type": "dto_office"}).json()
    assert {item["entity_type"] for item in filtered["items"]} == {"dto_office"}


def test_login_and_logout_are_audited(admin_client: TestClient, db: Session) -> None:
    admin_client.post("/api/auth/logout")
    actions = list(db.scalars(select(AuditLog.action).where(AuditLog.entity_type == "user")))
    assert "user.login" in actions and "user.logout" in actions


# --------------------------------------------------------------- jurisdiction


def test_state_admin_and_state_viewer_cover_everything(make_user: MakeUser, m: Masters) -> None:
    for user in (make_user(Role.STATE_ADMIN), make_user(Role.VIEWER)):
        jurisdiction = jurisdiction_of(user)
        assert jurisdiction.level == Level.STATE
        assert jurisdiction.covers_district(m.tinsukia.id)
        assert jurisdiction.covers_police_station(m.silchar.id, m.cachar.id)


def test_dto_dc_and_district_viewer_cover_only_their_district(
    make_user: MakeUser, m: Masters
) -> None:
    for user in (
        make_user(Role.DTO, dto_office=m.dto_tinsukia),
        make_user(Role.DC_OFFICE, district=m.tinsukia),
        make_user(Role.VIEWER, district=m.tinsukia),
    ):
        jurisdiction = jurisdiction_of(user)
        assert jurisdiction.level == Level.DISTRICT
        assert jurisdiction.district_id == m.tinsukia.id
        assert jurisdiction.covers_district(m.tinsukia.id)
        assert not jurisdiction.covers_district(m.cachar.id)
        assert jurisdiction.covers_police_station(m.margherita.id, m.tinsukia.id)
        assert not jurisdiction.covers_police_station(m.silchar.id, m.cachar.id)

        require_district(user, m.tinsukia.id)
        with pytest.raises(PermissionDeniedError):
            require_district(user, m.cachar.id)


def test_police_station_covers_only_itself(make_user: MakeUser, m: Masters) -> None:
    user = make_user(Role.POLICE_STATION, police_station=m.margherita)
    jurisdiction = jurisdiction_of(user)

    assert jurisdiction.level == Level.POLICE_STATION
    assert jurisdiction.covers_police_station(m.margherita.id, m.tinsukia.id)
    assert not jurisdiction.covers_police_station(m.digboi.id, m.tinsukia.id)
    # A police station does not see its whole district.
    assert not jurisdiction.covers_district(m.tinsukia.id)

    require_police_station(user, m.margherita.id, m.tinsukia.id)
    with pytest.raises(PermissionDeniedError):
        require_police_station(user, m.digboi.id, m.tinsukia.id)


def test_jurisdiction_follows_a_police_station_moved_to_another_district(
    admin_client: TestClient, make_user: MakeUser, m: Masters, db: Session
) -> None:
    user = make_user(Role.POLICE_STATION, police_station=m.digboi)
    admin_client.patch(
        f"/api/admin/police-stations/{m.digboi.id}", json={"district_id": m.cachar.id}
    )
    db.refresh(user.police_station)
    assert jurisdiction_of(user).district_id == m.cachar.id
