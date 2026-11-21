"""State Admin: creating officers, resetting passwords, bulk creation, permissions."""

import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models import AuditLog, Role, User
from tests.conftest import PASSWORD, Login, MakeUser, Masters

_PLACEHOLDERS = {
    "{district_id}": "1",
    "{station_id}": "1",
    "{office_id}": "1",
    "{user_pk}": "1",
    "{key}": "session_hours",
    "{type_id}": "1",
    "{contact_id}": "1",
    "{row_id}": "1",
}


def _fill(path: str) -> str:
    for placeholder, value in _PLACEHOLDERS.items():
        path = path.replace(placeholder, value)
    return path


# Taken from the API description, so a new admin route is checked automatically.
ADMIN_ROUTES = sorted(
    (method.upper(), _fill(path))
    for path, operations in app.openapi()["paths"].items()
    if path.startswith("/api/admin")
    for method in operations
)


def _sheet(response) -> list[tuple]:
    workbook = load_workbook(io.BytesIO(response.content))
    return list(workbook.active.iter_rows(values_only=True))


def test_there_are_admin_routes_to_check() -> None:
    assert len(ADMIN_ROUTES) >= 20


@pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
def test_every_admin_route_refuses_anonymous_and_non_admin_users(
    method: str, path: str, client: TestClient, make_user: MakeUser, login: Login, m: Masters
) -> None:
    assert client.request(method, path).status_code == 401

    for role, link in [
        (Role.DTO, {"dto_office": m.dto_tinsukia}),
        (Role.POLICE_STATION, {"police_station": m.margherita}),
        (Role.DC_OFFICE, {"district": m.tinsukia}),
        (Role.VIEWER, {}),
    ]:
        user = make_user(role, **link)
        assert login(client, user.user_id).status_code == 200
        response = client.request(method, path)
        assert response.status_code == 403, f"{role} reached {method} {path}"
        client.post("/api/auth/logout")


def test_create_user_generates_id_and_password_shown_once(
    admin_client: TestClient, anonymous: TestClient, login: Login, m: Masters
) -> None:
    response = admin_client.post(
        "/api/admin/users", json={"role": "POLICE_STATION", "police_station_id": m.margherita.id}
    )
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["user"]["user_id"] == "ps.margherita"
    assert body["user"]["office"] == "Margherita PS"
    assert body["user"]["status"] == "MUST_CHANGE_PASSWORD"
    assert len(body["password"]) == 10

    listed = admin_client.get("/api/admin/users", params={"search": "margherita"}).json()
    assert listed["total"] == 1
    assert "password" not in listed["items"][0]

    logged_in = login(anonymous, "ps.margherita", body["password"])
    assert logged_in.status_code == 200
    assert logged_in.json()["must_change_password"] is True
    assert logged_in.json()["jurisdiction_level"] == "POLICE_STATION"


def test_suggested_user_id_matches_the_created_one(admin_client: TestClient, m: Masters) -> None:
    suggested = admin_client.get(
        "/api/admin/users/suggest-id", params={"role": "DTO", "dto_office_id": m.dto_cachar.id}
    ).json()["user_id"]
    created = admin_client.post(
        "/api/admin/users", json={"role": "DTO", "dto_office_id": m.dto_cachar.id}
    ).json()["user"]["user_id"]
    assert suggested == created == "dto.cachar"


def test_create_user_needs_the_office_that_fits_the_role(
    admin_client: TestClient, m: Masters
) -> None:
    assert admin_client.post("/api/admin/users", json={"role": "DTO"}).status_code == 400
    assert admin_client.post("/api/admin/users", json={"role": "POLICE_STATION"}).status_code == 400
    assert admin_client.post("/api/admin/users", json={"role": "DC_OFFICE"}).status_code == 400


def test_custom_user_id_is_validated_and_must_be_free(admin_client: TestClient, m: Masters) -> None:
    bad = admin_client.post(
        "/api/admin/users", json={"role": "VIEWER", "user_id": "Transport State"}
    )
    assert bad.status_code == 400

    ok = admin_client.post("/api/admin/users", json={"role": "VIEWER", "user_id": "CS.Office"})
    assert ok.status_code == 201
    assert ok.json()["user"]["user_id"] == "cs.office"

    again = admin_client.post("/api/admin/users", json={"role": "VIEWER", "user_id": "cs.office"})
    assert again.status_code == 409


def test_reset_password_logs_the_user_out_and_forces_a_change(
    admin_client: TestClient,
    anonymous: TestClient,
    make_user: MakeUser,
    login: Login,
    m: Masters,
    db: Session,
) -> None:
    user = make_user(Role.DTO, dto_office=m.dto_tinsukia)
    login(anonymous, user.user_id)
    assert anonymous.get("/api/auth/me").status_code == 200

    response = admin_client.post(f"/api/admin/users/{user.id}/reset-password")
    assert response.status_code == 200
    new_password = response.json()["password"]

    assert anonymous.get("/api/auth/me").status_code == 401
    assert login(anonymous, user.user_id, PASSWORD).status_code == 401
    relogin = login(anonymous, user.user_id, new_password)
    assert relogin.status_code == 200
    assert relogin.json()["must_change_password"] is True

    audit_row = db.scalar(select(AuditLog).where(AuditLog.action == "user.password_reset"))
    assert audit_row.entity_label == "dto.tinsukia"
    assert new_password not in str(audit_row.new_value)


def test_reset_password_unlocks_a_locked_account(
    admin_client: TestClient, make_user: MakeUser, login: Login, m: Masters, db: Session
) -> None:
    user = make_user(Role.DTO, dto_office=m.dto_tinsukia)
    for _ in range(5):
        login(admin_client, user.user_id, "wrong-password1")
    assert db.get(User, user.id).locked_until is not None

    admin_client.post(f"/api/admin/users/{user.id}/reset-password")
    assert db.get(User, user.id).locked_until is None


def test_first_passwords_are_generated_once_as_an_excel_download(
    admin_client: TestClient,
    anonymous: TestClient,
    make_user: MakeUser,
    login: Login,
    m: Masters,
) -> None:
    make_user(Role.DTO, dto_office=m.dto_tinsukia, password=None)
    make_user(Role.DC_OFFICE, district=m.tinsukia, password=None)
    make_user(Role.POLICE_STATION, police_station=m.digboi)  # already has a password

    pending = admin_client.get("/api/admin/users/pending-passwords").json()
    assert pending["never_issued"] == 2

    response = admin_client.post("/api/admin/users/generate-passwords")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "attachment" in response.headers["content-disposition"]
    rows = _sheet(response)
    assert rows[0] == ("User ID", "Password", "Role", "Office", "District")
    assert [row[0] for row in rows[1:]] == ["dc.tinsukia", "dto.tinsukia"]
    assert rows[2][2:] == ("DTO", "District Transport Office, Tinsukia", "Tinsukia")

    credentials = {row[0]: row[1] for row in rows[1:]}
    logged_in = login(anonymous, "dto.tinsukia", credentials["dto.tinsukia"])
    assert logged_in.status_code == 200
    assert logged_in.json()["must_change_password"] is True

    # A second click issues nothing: the passwords cannot be downloaded again.
    assert len(_sheet(admin_client.post("/api/admin/users/generate-passwords"))) == 1
    assert admin_client.get("/api/admin/users/pending-passwords").json()["never_issued"] == 0


def test_lost_download_can_be_reissued_for_accounts_that_never_logged_in(
    admin_client: TestClient,
    anonymous: TestClient,
    make_user: MakeUser,
    login: Login,
    m: Masters,
) -> None:
    make_user(Role.DTO, dto_office=m.dto_tinsukia, password=None)
    make_user(Role.DC_OFFICE, district=m.tinsukia, password=None)
    first = {r[0]: r[1] for r in _sheet(admin_client.post("/api/admin/users/generate-passwords"))}
    login(anonymous, "dc.tinsukia", first["dc.tinsukia"])  # this officer has logged in

    again = _sheet(
        admin_client.post(
            "/api/admin/users/generate-passwords", params={"include_never_logged_in": True}
        )
    )
    reissued = {row[0]: row[1] for row in again[1:]}
    assert set(reissued) == {"dto.tinsukia"}
    assert reissued["dto.tinsukia"] != first["dto.tinsukia"]


def test_deactivating_a_user_ends_the_session_and_blocks_login(
    admin_client: TestClient, anonymous: TestClient, make_user: MakeUser, login: Login, m: Masters
) -> None:
    user = make_user(Role.DTO, dto_office=m.dto_tinsukia)
    login(anonymous, user.user_id)

    response = admin_client.patch(f"/api/admin/users/{user.id}", json={"is_active": False})
    assert response.json()["status"] == "INACTIVE"
    assert anonymous.get("/api/auth/me").status_code == 401
    assert login(anonymous, user.user_id).status_code == 401

    admin_client.patch(f"/api/admin/users/{user.id}", json={"is_active": True})
    assert login(anonymous, user.user_id).status_code == 200


def test_admin_cannot_deactivate_self_or_the_last_admin(
    admin_client: TestClient, admin: User
) -> None:
    response = admin_client.patch(f"/api/admin/users/{admin.id}", json={"is_active": False})
    assert response.status_code == 400


def test_user_id_can_be_renamed_and_the_office_link_stays(
    admin_client: TestClient,
    anonymous: TestClient,
    make_user: MakeUser,
    login: Login,
    m: Masters,
) -> None:
    user = make_user(Role.DTO, dto_office=m.dto_tinsukia)

    response = admin_client.patch(f"/api/admin/users/{user.id}", json={"user_id": "DTO.Tsk"})
    assert response.status_code == 200
    assert response.json()["user_id"] == "dto.tsk"
    assert response.json()["office"] == "District Transport Office, Tinsukia"

    assert login(anonymous, "dto.tinsukia").status_code == 401
    assert login(anonymous, "dto.tsk").status_code == 200

    taken = admin_client.patch(f"/api/admin/users/{user.id}", json={"user_id": "admin.1"})
    assert taken.status_code == 409


def test_users_can_be_filtered_by_role_and_district(
    admin_client: TestClient, make_user: MakeUser, m: Masters
) -> None:
    make_user(Role.DTO, dto_office=m.dto_tinsukia)
    make_user(Role.POLICE_STATION, police_station=m.margherita)
    make_user(Role.DC_OFFICE, district=m.cachar)

    in_tinsukia = admin_client.get("/api/admin/users", params={"district_id": m.tinsukia.id}).json()
    assert {u["user_id"] for u in in_tinsukia["items"]} == {"dto.tinsukia", "ps.margherita"}

    dc_only = admin_client.get("/api/admin/users", params={"role": "DC_OFFICE"}).json()
    assert [u["user_id"] for u in dc_only["items"]] == ["dc.cachar"]


# ---------------------------------------------------------------- bulk create


def _csv(text: str) -> dict:
    return {"file": ("users.csv", text.encode(), "text/csv")}


def test_bulk_create_returns_user_ids_and_passwords(
    admin_client: TestClient, anonymous: TestClient, login: Login, m: Masters
) -> None:
    response = admin_client.post(
        "/api/admin/users/bulk",
        files=_csv(
            "Role,District ID,Police Station Name,User ID\n"
            "DTO,1022,,\n"
            "DC Office,1022,,\n"
            "Police Station,1022,Margherita PS,\n"
            "Police Station,1022,digboi ps,\n"
            "Viewer,1022,,\n"
            "Viewer,,,transport.state.1\n"
        ),
    )
    assert response.status_code == 200
    rows = _sheet(response)
    assert [row[0] for row in rows[1:]] == [
        "dto.tinsukia",
        "dc.tinsukia",
        "ps.margherita",
        "ps.digboi",
        "sp.tinsukia",
        "transport.state.1",
    ]
    assert login(anonymous, "ps.digboi", rows[4][1]).status_code == 200


def test_bulk_create_is_all_or_nothing(admin_client: TestClient, m: Masters, db: Session) -> None:
    response = admin_client.post(
        "/api/admin/users/bulk",
        files=_csv(
            "Role,District ID,Police Station Name\n"
            "DTO,1022,\n"
            "Police Station,1022,Nowhere PS\n"
            "Clerk,1022,\n"
        ),
    )
    assert response.status_code == 400
    body = response.json()
    assert "No users were created" in body["detail"]
    assert len(body["errors"]) == 2
    assert body["errors"][0].startswith("Row 3:")
    assert db.scalar(select(User).where(User.user_id == "dto.tinsukia")) is None


def test_bulk_create_rejects_a_file_without_the_columns(admin_client: TestClient) -> None:
    response = admin_client.post("/api/admin/users/bulk", files=_csv("Name,Place\nA,B\n"))
    assert response.status_code == 400
    assert "missing these columns" in response.json()["detail"]


def test_bulk_template_downloads(admin_client: TestClient) -> None:
    rows = _sheet(admin_client.get("/api/admin/users/bulk-template"))
    assert rows[0] == ("Role", "District ID", "Police Station Name", "User ID")


# ------------------------------------------------------------------- settings


def test_settings_start_with_the_agreed_values(admin_client: TestClient) -> None:
    rows = admin_client.get("/api/admin/settings").json()
    values = {s["key"]: s["value"] for s in rows}
    assert values == {
        "applicant_session_minutes": 30,
        "applications_per_mobile_per_day": 3,
        "captcha_valid_minutes": 5,
        "child_free_below_age": 0,
        "earliest_departure_hour": 7,
        "generated_password_length": 10,
        "latest_return_hour": 18,
        "leader_min_age": 18,
        "login_lock_minutes": 15,
        "login_max_failed_attempts": 5,
        "max_days_before_travel": 90,
        "min_days_before_travel": 7,
        "otp_length": 6,
        "otp_max_attempts": 3,
        "otp_max_per_hour": 5,
        "otp_resend_seconds": 60,
        "otp_valid_minutes": 5,
        "password_min_length": 8,
        "session_hours": 48,
        "temp_upload_hours": 24,
        "upload_max_mb": 5,
    }
    # The rows created by the migrations and the defaults in the code must agree.
    from app.services.settings import SPECS

    assert {
        (s["key"], s["value"], s["min_value"], s["max_value"], s["description"]) for s in rows
    } == {(s.key, s.default, s.min_value, s.max_value, s.description) for s in SPECS}


def test_setting_change_takes_effect_and_is_range_checked(
    admin_client: TestClient, make_user: MakeUser, login: Login, m: Masters, db: Session
) -> None:
    ok = admin_client.patch("/api/admin/settings/login_max_failed_attempts", json={"value": 3})
    assert ok.status_code == 200
    assert (
        admin_client.patch(
            "/api/admin/settings/login_max_failed_attempts", json={"value": 1}
        ).status_code
        == 400
    )
    assert admin_client.patch("/api/admin/settings/nope", json={"value": 1}).status_code == 404

    user = make_user(Role.DTO, dto_office=m.dto_tinsukia)
    for _ in range(3):
        login(admin_client, user.user_id, "wrong-password1")
    assert db.get(User, user.id).locked_until is not None
