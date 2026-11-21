"""Login, captcha, lockout, sessions and password change."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.models import Captcha, Role, User, UserSession
from app.services import captcha
from tests.conftest import PASSWORD, Login, MakeUser, Masters


def test_captcha_is_a_png_image_and_hides_the_answer(client: TestClient) -> None:
    body = client.get("/api/auth/captcha").json()
    assert body["enabled"] is True
    assert body["image"].startswith("data:image/png;base64,")
    assert set(body) == {"enabled", "captcha_id", "image"}


def test_login_sets_a_cookie_and_me_returns_the_officer(
    client: TestClient, make_user: MakeUser, login: Login, m: Masters
) -> None:
    make_user(Role.DTO, dto_office=m.dto_tinsukia)

    response = login(client, "dto.tinsukia")

    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "pp_session=" in cookie and "httponly" in cookie and "samesite=lax" in cookie
    me = client.get("/api/auth/me").json()
    assert me["user_id"] == "dto.tinsukia"
    assert me["role"] == "DTO"
    assert me["office"] == "District Transport Office, Tinsukia"
    assert me["jurisdiction_level"] == "DISTRICT"
    assert me["district_name"] == "Tinsukia"


def test_login_user_id_is_not_case_sensitive(
    client: TestClient, make_user: MakeUser, login: Login, m: Masters
) -> None:
    make_user(Role.DTO, dto_office=m.dto_tinsukia)
    assert login(client, "  DTO.Tinsukia ").status_code == 200


def test_session_lasts_48_hours(client: TestClient, admin: User, login: Login, db: Session) -> None:
    response = login(client, admin.user_id)
    assert "max-age=172800" in response.headers["set-cookie"].lower()
    session = db.scalar(select(UserSession).where(UserSession.user_id == admin.id))
    assert session.expires_at - session.created_at == timedelta(hours=48)


def test_expired_session_is_refused(
    client: TestClient, admin: User, login: Login, db: Session
) -> None:
    login(client, admin.user_id)
    session = db.scalar(select(UserSession).where(UserSession.user_id == admin.id))
    session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert client.get("/api/auth/me").status_code == 401


def test_me_without_login_is_401(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 401


def test_wrong_captcha_is_refused_before_the_password_is_checked(
    client: TestClient, admin: User, db: Session
) -> None:
    captcha_id, _answer, _ = captcha.create(db)
    db.commit()
    response = client.post(
        "/api/auth/login",
        json={
            "user_id": admin.user_id,
            "password": PASSWORD,
            "captcha_id": captcha_id,
            "captcha_answer": "WRONG",
        },
    )
    assert response.status_code == 400
    assert "captcha" in response.json()["detail"].lower()
    assert db.get(User, admin.id).failed_attempts == 0


def test_login_without_a_captcha_is_refused(client: TestClient, admin: User) -> None:
    response = client.post("/api/auth/login", json={"user_id": admin.user_id, "password": PASSWORD})
    assert response.status_code == 400


def test_a_captcha_works_only_once(client: TestClient, admin: User, db: Session) -> None:
    captcha_id, answer, _ = captcha.create(db)
    db.commit()
    payload = {
        "user_id": admin.user_id,
        "password": PASSWORD,
        "captcha_id": captcha_id,
        "captcha_answer": answer.lower(),
    }
    assert client.post("/api/auth/login", json=payload).status_code == 200
    assert client.post("/api/auth/login", json=payload).status_code == 400


def test_an_expired_captcha_is_refused(db: Session) -> None:
    captcha_id, answer, _ = captcha.create(db)
    db.flush()
    db.get(Captcha, captcha_id).expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.flush()
    assert captcha.verify(db, captcha_id, answer) is False


def test_wrong_password_and_unknown_user_give_the_same_answer(
    client: TestClient, admin: User, login: Login
) -> None:
    wrong = login(client, admin.user_id, "not-the-password1")
    unknown = login(client, "dto.nowhere", PASSWORD)
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_account_locks_after_5_wrong_passwords_for_15_minutes(
    client: TestClient, admin: User, login: Login, db: Session
) -> None:
    for _ in range(4):
        assert login(client, admin.user_id, "wrong-password1").status_code == 401
    assert db.get(User, admin.id).locked_until is None

    assert login(client, admin.user_id, "wrong-password1").status_code == 401
    locked_until = db.get(User, admin.id).locked_until
    assert timedelta(minutes=14) < locked_until - datetime.now(UTC) <= timedelta(minutes=15)

    # Even the right password is refused while the account is locked.
    response = login(client, admin.user_id)
    assert response.status_code == 423
    assert "locked" in response.json()["detail"]


def test_account_unlocks_when_the_lock_time_has_passed(
    client: TestClient, admin: User, login: Login, db: Session
) -> None:
    admin.locked_until = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert login(client, admin.user_id).status_code == 200
    assert db.get(User, admin.id).locked_until is None


def test_a_correct_login_resets_the_wrong_attempt_count(
    client: TestClient, admin: User, login: Login, db: Session
) -> None:
    for _ in range(3):
        login(client, admin.user_id, "wrong-password1")
    assert login(client, admin.user_id).status_code == 200
    assert db.get(User, admin.id).failed_attempts == 0


def test_account_without_a_password_cannot_log_in(
    client: TestClient, make_user: MakeUser, login: Login, m: Masters
) -> None:
    make_user(Role.DC_OFFICE, district=m.tinsukia, password=None)
    assert login(client, "dc.tinsukia", "").status_code == 422
    assert login(client, "dc.tinsukia", "anything1").status_code == 401


def test_inactive_account_cannot_log_in(
    client: TestClient, make_user: MakeUser, login: Login, m: Masters, db: Session
) -> None:
    user = make_user(Role.DC_OFFICE, district=m.tinsukia)
    user.is_active = False
    db.commit()
    assert login(client, "dc.tinsukia").status_code == 401


def test_logout_ends_the_session(client: TestClient, admin: User, login: Login) -> None:
    login(client, admin.user_id)
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_state_changing_request_without_the_portal_header_is_refused(
    client: TestClient, admin: User, login: Login
) -> None:
    login(client, admin.user_id)
    response = client.post("/api/auth/logout", headers={"X-Requested-With": ""})
    assert response.status_code == 403
    assert client.get("/api/auth/me").status_code == 200


# ------------------------------------------------------- forced password change


def test_generated_password_must_be_changed_before_anything_else(
    client: TestClient, make_user: MakeUser, login: Login
) -> None:
    admin = make_user(Role.STATE_ADMIN, must_change_password=True)

    response = login(client, admin.user_id)
    assert response.status_code == 200
    assert response.json()["must_change_password"] is True

    assert client.get("/api/auth/me").status_code == 200
    blocked = client.get("/api/admin/users")
    assert blocked.status_code == 403
    assert "Change your password" in blocked.json()["detail"]

    changed = client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "Brandnew2026"},
    )
    assert changed.status_code == 204
    assert client.get("/api/auth/me").json()["must_change_password"] is False
    assert client.get("/api/admin/users").status_code == 200


@pytest.mark.parametrize(
    ("new_password", "reason"),
    [
        ("Short1a", "at least 8 characters"),
        ("12345678", "at least 1 letter"),
        ("abcdefgh", "at least 1 digit"),
        (PASSWORD, "different from the current"),
    ],
)
def test_password_rule(
    client: TestClient, admin: User, login: Login, new_password: str, reason: str
) -> None:
    login(client, admin.user_id)
    response = client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": new_password},
    )
    assert response.status_code == 400
    assert reason in response.json()["detail"]


def test_password_must_not_equal_the_user_id() -> None:
    problem = security.password_rule_problem("Admin.12345", user_id="admin.12345", min_length=8)
    assert problem is not None and "user ID" in problem


def test_change_password_needs_the_current_password(
    client: TestClient, admin: User, login: Login
) -> None:
    login(client, admin.user_id)
    response = client.post(
        "/api/auth/change-password",
        json={"current_password": "not-right-1", "new_password": "Brandnew2026"},
    )
    assert response.status_code == 400


def test_changing_the_password_logs_out_other_sessions(
    client: TestClient, anonymous: TestClient, admin: User, login: Login
) -> None:
    login(client, admin.user_id)
    login(anonymous, admin.user_id)
    assert anonymous.get("/api/auth/me").status_code == 200

    client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "Brandnew2026"},
    )

    assert client.get("/api/auth/me").status_code == 200
    assert anonymous.get("/api/auth/me").status_code == 401
    assert login(anonymous, admin.user_id, "Brandnew2026").status_code == 200


def test_generated_passwords_follow_the_password_rule() -> None:
    for _ in range(50):
        password = security.generate_password(10)
        assert len(password) == 10
        assert security.password_rule_problem(password, user_id="dto.x", min_length=8) is None


def test_passwords_are_stored_only_as_argon2_hashes(admin: User) -> None:
    assert admin.password_hash.startswith("$argon2id$")
    assert PASSWORD not in admin.password_hash
