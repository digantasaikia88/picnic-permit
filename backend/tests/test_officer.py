"""The three offices: who sees what, every workflow move and who may make it."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.models import (
    Application,
    AuditLog,
    DocType,
    RemarkReason,
    Role,
    SmsLog,
    Status,
    User,
    WorkingStatus,
)
from app.services import access, workflow
from app.services.access import Acting
from tests import formkit
from tests.conftest import Login, MakeUser, Masters
from tests.formkit import OFFICER, PDF, day, office_user, payload, submit

OTHER_MOBILE = "9876511111"


def new_application(client: TestClient, db: Session, m: Masters, **changes) -> Application:
    response = submit(client, db, payload(db, m, **changes))
    assert response.status_code == 201, response.text
    number = response.json()["application_number"]
    application = db.scalar(select(Application).where(Application.application_number == number))
    # These tests are about who may move an application. What each office must
    # record before it forwards is tested in test_officer_work.py.
    formkit.make_ready(db, application)
    return application


def at_stage(db: Session, application: Application, stage: Status) -> Application:
    """Move an application to a stage through the real workflow."""
    order = [Status.PENDING_DTO, Status.PENDING_POLICE, Status.PENDING_DC, Status.APPROVED]
    while application.status != stage:
        assert order.index(application.status) < order.index(stage)
        workflow.forward(db, application, acting=formkit.acting_for(db, application))
    db.commit()
    return application


def as_office(
    client: TestClient, db: Session, login: Login, application: Application, role: Role
) -> User:
    user = office_user(db, application, role)
    db.commit()
    client.post("/api/auth/logout")
    assert login(client, user.user_id).status_code == 200
    return user


def url(application: Application, action: str = "") -> str:
    return f"/api/officer/applications/{application.id}" + (f"/{action}" if action else "")


# ------------------------------------------------------------ the full path


def test_application_goes_dto_then_police_then_dc_and_is_approved(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = new_application(client, db, m)

    as_office(client, db, login, application, Role.DTO)
    first = client.post(
        url(application, "forward"), json={**OFFICER, "remarks": "Vehicle in order"}
    )
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "PENDING_POLICE"
    assert first.json()["current_office"] == "Margherita PS"
    assert first.json()["with_my_office"] is False

    as_office(client, db, login, application, Role.POLICE_STATION)
    second = client.post(url(application, "forward"), json=OFFICER)
    assert second.json()["status"] == "PENDING_DC"
    assert second.json()["current_office"] == "DC Office, Tinsukia"

    as_office(client, db, login, application, Role.DC_OFFICE)
    third = client.post(url(application, "forward"), json=OFFICER)
    assert third.json()["status"] == "APPROVED"
    assert third.json()["forward_label"] is None

    kinds = [s.kind for s in db.scalars(select(SmsLog).order_by(SmsLog.id)) if s.kind != "OTP"]
    assert kinds == [
        "APPLICATION_SUBMITTED",
        "APPLICATION_FORWARDED",
        "APPLICATION_FORWARDED",
        "APPLICATION_APPROVED",
    ]
    approved = db.scalar(select(SmsLog).where(SmsLog.kind == "APPLICATION_APPROVED"))
    assert f"Permit number {application.application_number}" in approved.message
    assert "Download the permit" in approved.message

    titles = [entry["title"] for entry in third.json()["timeline"]]
    assert titles == ["Submitted by the applicant", "Forwarded", "Forwarded", "Approved"]


def test_every_action_records_the_officers_name_and_designation(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = new_application(client, db, m)
    user = as_office(client, db, login, application, Role.DTO)

    client.post(
        url(application, "forward"),
        json={"officer_name": " Dipak  Saikia ", "officer_designation": "MVI", "remarks": "OK"},
    )

    row = db.scalar(select(AuditLog).where(AuditLog.action == "application.forwarded"))
    assert row.actor_user_id == user.id and row.actor_label == user.user_id
    assert (row.officer_name, row.officer_designation) == ("Dipak  Saikia", "MVI")
    assert row.old_value == {"status": "PENDING_DTO"}
    assert row.new_value == {"status": "PENDING_POLICE", "remarks": "OK"}

    missing = client.post(url(application, "forward"), json={"remarks": "x"})
    assert missing.status_code == 422


@pytest.mark.parametrize(
    ("stage", "role", "label"),
    [
        (Status.PENDING_DTO, Role.DTO, "Forward to the police station"),
        (Status.PENDING_POLICE, Role.POLICE_STATION, "Forward to the DC office"),
        (Status.PENDING_DC, Role.DC_OFFICE, "Approve"),
    ],
)
def test_forward_button_says_what_it_does_at_each_stage(
    client: TestClient, db: Session, m: Masters, login: Login, stage: Status, role: Role, label: str
) -> None:
    application = at_stage(db, new_application(client, db, m), stage)
    as_office(client, db, login, application, role)
    assert client.get(url(application)).json()["forward_label"] == label


# ---------------------------------------------- who may act at which stage

ACTIONS = {
    "forward": OFFICER,
    "return": {**OFFICER, "remarks": "Please correct the RC."},
    "reject": {**OFFICER, "remarks": "Not eligible."},
    "working-status": {**OFFICER, "working_status_id": None},
}


@pytest.mark.parametrize("action", sorted(ACTIONS))
@pytest.mark.parametrize("role", access.WORKFLOW_ROLES)
@pytest.mark.parametrize("stage", workflow.PENDING_STATUSES)
def test_an_office_acts_only_while_the_application_is_at_its_own_stage(
    client: TestClient,
    db: Session,
    m: Masters,
    login: Login,
    stage: Status,
    role: Role,
    action: str,
) -> None:
    application = at_stage(db, new_application(client, db, m), stage)
    as_office(client, db, login, application, role)

    response = client.post(url(application, action), json=ACTIONS[action])

    if access.STAGE_OF_ROLE[role] == stage:
        assert response.status_code == 200, response.text
    else:
        assert response.status_code == 403
        assert "not pending with your office" in response.json()["detail"]
        db.refresh(application)
        assert application.status == stage


@pytest.mark.parametrize(
    "status", [Status.APPROVED, Status.REJECTED, Status.RETURNED_TO_APPLICANT, Status.EXPIRED]
)
@pytest.mark.parametrize("action", sorted(ACTIONS))
def test_nobody_acts_on_an_application_that_no_office_holds(
    client: TestClient, db: Session, m: Masters, login: Login, status: Status, action: str
) -> None:
    application = new_application(client, db, m)
    application.status = status
    db.commit()
    for role in access.WORKFLOW_ROLES:
        as_office(client, db, login, application, role)
        assert client.post(url(application, action), json=ACTIONS[action]).status_code == 403


def test_admin_viewer_and_anonymous_cannot_use_the_officer_pages(
    client: TestClient, db: Session, m: Masters, login: Login, make_user: MakeUser
) -> None:
    application = new_application(client, db, m)
    assert client.get("/api/officer/queue").status_code == 401
    assert client.get(url(application)).status_code == 401

    for user in (make_user(Role.STATE_ADMIN), make_user(Role.VIEWER, district=m.tinsukia)):
        assert login(client, user.user_id).status_code == 200
        assert client.get("/api/officer/queue").status_code == 403
        assert client.get(url(application)).status_code == 403
        assert client.post(url(application, "forward"), json=OFFICER).status_code == 403
        client.post("/api/auth/logout")


# ------------------------------------------------------------ jurisdiction


def test_offices_of_another_district_or_station_cannot_see_or_touch_an_application(
    client: TestClient, db: Session, m: Masters, login: Login, make_user: MakeUser
) -> None:
    application = at_stage(db, new_application(client, db, m), Status.PENDING_POLICE)
    document = application.documents[0]
    outsiders = [
        make_user(Role.DTO, dto_office=m.dto_cachar),
        make_user(Role.DC_OFFICE, district=m.cachar),
        make_user(Role.POLICE_STATION, police_station=m.silchar),
        # Another station of the same district is outside too.
        make_user(Role.POLICE_STATION, police_station=m.digboi),
    ]
    for user in outsiders:
        assert login(client, user.user_id).status_code == 200
        assert client.get(url(application)).status_code == 404, user.user_id
        assert client.get(url(application, f"documents/{document.id}")).status_code == 404
        for action, body in ACTIONS.items():
            assert client.post(url(application, action), json=body).status_code == 404
        assert client.get("/api/officer/queue").json() == []
        assert client.get("/api/officer/applications").json()["total"] == 0
        client.post("/api/auth/logout")


def test_each_office_sees_its_own_queue_only(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    at_dto = new_application(client, db, m)
    at_police = at_stage(
        db,
        new_application(client, db, m, vehicle_reg_number="AS23C0002", licence_number="AS23X0002"),
        Status.PENDING_POLICE,
    )
    at_dc = at_stage(
        db,
        new_application(client, db, m, vehicle_reg_number="AS23C0003", licence_number="AS23X0003"),
        Status.PENDING_DC,
    )

    def queue_of(role: Role) -> list[str]:
        as_office(client, db, login, at_dto, role)
        return [item["application_number"] for item in client.get("/api/officer/queue").json()]

    assert queue_of(Role.DTO) == [at_dto.application_number]
    assert queue_of(Role.POLICE_STATION) == [at_police.application_number]
    assert queue_of(Role.DC_OFFICE) == [at_dc.application_number]


def test_dc_office_sees_every_application_of_the_district_from_submission(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = new_application(client, db, m)
    in_cachar = new_application(
        client,
        db,
        m,
        vehicle_reg_number="AS11C0002",
        licence_number="AS11X0002",
        origin_district_id=m.cachar.id,
        origin_police_station_id=m.silchar.id,
    )
    as_office(client, db, login, application, Role.DC_OFFICE)

    listed = client.get("/api/officer/applications").json()
    assert [a["application_number"] for a in listed["items"]] == [application.application_number]
    assert listed["items"][0]["with_my_office"] is False
    assert client.get("/api/officer/queue").json() == []

    # It can look, but not act, until the police forward it.
    detail = client.get(url(application))
    assert detail.status_code == 200 and detail.json()["forward_label"] is None
    assert client.get(url(in_cachar)).status_code == 404


def test_police_station_sees_only_applications_that_name_it(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    mine = new_application(client, db, m)
    other_station = new_application(
        client,
        db,
        m,
        vehicle_reg_number="AS23C0002",
        licence_number="AS23X0002",
        origin_police_station_id=m.digboi.id,
    )
    as_office(client, db, login, mine, Role.POLICE_STATION)

    listed = client.get("/api/officer/applications").json()
    assert [a["application_number"] for a in listed["items"]] == [mine.application_number]
    assert client.get(url(other_station)).status_code == 404


def test_queue_is_sorted_by_travel_date_with_days_left_and_can_be_searched(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    later = new_application(client, db, m, travel_date=day(30).isoformat())
    sooner = new_application(
        client,
        db,
        m,
        travel_date=day(8).isoformat(),
        vehicle_reg_number="AS 23 C 0002",
        licence_number="AS23X0002",
        leader_mobile=OTHER_MOBILE,
    )
    as_office(client, db, login, later, Role.DTO)

    queue = client.get("/api/officer/queue").json()
    assert [(q["application_number"], q["days_left"]) for q in queue] == [
        (sooner.application_number, 8),
        (later.application_number, 30),
    ]

    def found(search: str) -> list[str]:
        rows = client.get("/api/officer/queue", params={"search": search}).json()
        return [q["application_number"] for q in rows]

    assert found(sooner.application_number) == [sooner.application_number]
    assert found("as-23-c-0002") == [sooner.application_number]
    assert found(OTHER_MOBILE) == [sooner.application_number]
    assert found("ZZ99") == []


# --------------------------------------------------------- application page


def test_office_sees_the_application_its_documents_and_alerts(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    earlier = new_application(client, db, m, travel_date=day(9).isoformat())
    earlier.status = Status.REJECTED
    earlier.status_remarks = "Vehicle failed inspection"
    application = new_application(client, db, m)
    other_leader_vehicle = new_application(
        client, db, m, vehicle_reg_number="AS23C0009", licence_number="AS23X0009"
    )
    as_office(client, db, login, application, Role.DTO)

    body = client.get(url(application)).json()

    assert body["form"]["leader_name"] == "Rupam Das"
    assert body["vehicle_type"] == "Car / SUV"
    assert len(body["documents"]) == 5 and len(body["passengers"]) == 3
    alerts = {a["application_number"]: a for a in body["alerts"]}
    assert set(alerts) == {earlier.application_number, other_leader_vehicle.application_number}
    rejected = alerts[earlier.application_number]
    assert (rejected["same_vehicle"], rejected["same_driver"], rejected["same_leader"]) == (
        True,
        True,
        True,
    )
    assert rejected["rejection_reason"] == "Vehicle failed inspection"
    same_leader = alerts[other_leader_vehicle.application_number]
    assert (same_leader["same_vehicle"], same_leader["same_leader"]) == (False, True)

    document = body["documents"][0]
    opened = client.get(url(application, f"documents/{document['id']}"))
    assert opened.status_code == 200 and opened.content == PDF
    assert opened.headers["cache-control"] == "no-store"


# ---------------------------------------------------------- return, reject


def test_return_needs_remarks_or_a_reason_and_comes_back_to_the_same_office(
    client: TestClient, anonymous: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = at_stage(db, new_application(client, db, m), Status.PENDING_POLICE)
    as_office(client, db, login, application, Role.POLICE_STATION)
    reason = db.scalar(select(RemarkReason).where(RemarkReason.name == "Document not readable"))

    assert client.post(url(application, "return"), json=OFFICER).status_code == 400

    returned = client.post(
        url(application, "return"),
        json={**OFFICER, "reason_id": reason.id, "remarks": "Page 2 of the RC."},
    )
    assert returned.status_code == 200
    assert returned.json()["status"] == "RETURNED_TO_APPLICANT"
    assert returned.json()["remarks"] == "Document not readable. Page 2 of the RC."

    public = anonymous.get(f"/api/public/status/{application.application_number}").json()
    assert public["remarks"] == "Document not readable. Page 2 of the RC."

    workflow.resubmit(db, application, vehicle_or_driver_changed=False)
    db.commit()
    assert application.status == Status.PENDING_POLICE
    queue = client.get("/api/officer/queue").json()
    assert [q["application_number"] for q in queue] == [application.application_number]


def test_reject_needs_a_reason_closes_the_application_and_frees_the_vehicle(
    client: TestClient, anonymous: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = new_application(client, db, m)
    as_office(client, db, login, application, Role.DTO)
    reason = db.scalar(
        select(RemarkReason).where(RemarkReason.kind == "REJECT", RemarkReason.name.like("Unpaid%"))
    )

    assert client.post(url(application, "reject"), json=OFFICER).status_code == 400
    wrong_kind = db.scalar(select(RemarkReason).where(RemarkReason.kind == "RETURN"))
    assert (
        client.post(
            url(application, "reject"), json={**OFFICER, "reason_id": wrong_kind.id}
        ).status_code
        == 404
    )

    rejected = client.post(url(application, "reject"), json={**OFFICER, "reason_id": reason.id})
    assert rejected.json()["status"] == "REJECTED"

    public = anonymous.get(f"/api/public/status/{application.application_number}").json()
    assert public["status_label"] == "Rejected"
    assert public["remarks"] == "Unpaid traffic challans"
    assert public["current_office"] == "Closed"

    message = db.scalar(select(SmsLog).where(SmsLog.kind == "APPLICATION_REJECTED"))
    assert "REJECTED by District Transport Office, Tinsukia" in message.message
    assert "Unpaid traffic challans" in message.message

    # The vehicle and driver are free again for that date: a fresh application goes through.
    again = submit(anonymous, db, payload(db, m, leader_mobile=OTHER_MOBILE))
    assert again.status_code == 201 and again.json()["status"] == "PENDING_DTO"
    # The office sees the earlier rejection as an alert on the new one.
    fresh = db.scalar(select(Application).where(Application.leader_mobile == OTHER_MOBILE))
    alert = client.get(url(fresh)).json()["alerts"][0]
    assert alert["rejection_reason"] == "Unpaid traffic challans"


# ----------------------------------------------------------- working status


def test_working_status_is_set_by_the_holding_office_and_shown_to_the_applicant(
    client: TestClient, anonymous: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = new_application(client, db, m)
    as_office(client, db, login, application, Role.DTO)
    scheduled = db.scalar(select(WorkingStatus).where(WorkingStatus.name == "Inspection scheduled"))
    public_url = f"/api/public/status/{application.application_number}"

    assert anonymous.get(public_url).json()["working_status"] == "Received"

    changed = client.post(
        url(application, "working-status"), json={**OFFICER, "working_status_id": scheduled.id}
    )
    assert changed.json()["working_status"] == "Inspection scheduled"
    assert anonymous.get(public_url).json()["working_status"] == "Inspection scheduled"

    row = db.scalar(select(AuditLog).where(AuditLog.action == "application.working_status"))
    assert row.old_value == {"working_status": "Received"}
    assert row.new_value == {"working_status": "Inspection scheduled"}
    assert row.officer_name == "A. Baruah"

    # The next office starts again from "Received".
    client.post(url(application, "forward"), json=OFFICER)
    assert anonymous.get(public_url).json()["working_status"] == "Received"

    # A closed application has no working status.
    db.refresh(application)
    application.status = Status.APPROVED
    db.commit()
    assert anonymous.get(public_url).json()["working_status"] is None


def test_working_status_must_be_an_active_one_from_the_list(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = new_application(client, db, m)
    as_office(client, db, login, application, Role.DTO)
    retired = db.scalar(select(WorkingStatus).where(WorkingStatus.name == "Inspection completed"))
    retired.is_active = False
    db.commit()

    for bad in (retired.id, 999999):
        response = client.post(
            url(application, "working-status"), json={**OFFICER, "working_status_id": bad}
        )
        assert response.status_code == 400

    names = [w["name"] for w in client.get("/api/officer/reference").json()["working_statuses"]]
    assert "Inspection completed" not in names and "Inspection scheduled" in names


OFFERED = {
    Role.DTO: [
        "Document verification in progress",
        "Awaiting documents from applicant",
        "Inspection scheduled",
        "Inspection completed",
        "Put up for approval",
    ],
    Role.POLICE_STATION: [
        "Verification in progress",
        "Field verification scheduled",
        "Put up for approval",
    ],
    Role.DC_OFFICE: ["Under review", "Put up for approval"],
}


@pytest.mark.parametrize(
    "stage, role",
    [
        (Status.PENDING_DTO, Role.DTO),
        (Status.PENDING_POLICE, Role.POLICE_STATION),
        (Status.PENDING_DC, Role.DC_OFFICE),
    ],
)
def test_each_office_is_offered_and_can_set_only_its_own_working_statuses(
    client: TestClient, db: Session, m: Masters, login: Login, stage: Status, role: Role
) -> None:
    application = at_stage(db, new_application(client, db, m), stage)
    as_office(client, db, login, application, role)

    offered = client.get("/api/officer/reference").json()["working_statuses"]
    assert [w["name"] for w in offered] == OFFERED[role]

    for row in db.scalars(select(WorkingStatus)):
        response = client.post(
            url(application, "working-status"), json={**OFFICER, "working_status_id": row.id}
        )
        expected = 200 if row.name in OFFERED[role] else 400
        assert response.status_code == expected, row.name


def test_admin_chooses_the_offices_of_a_working_status(
    admin_client: TestClient, db: Session
) -> None:
    rows = {row["name"]: row for row in admin_client.get("/api/admin/working-statuses").json()}
    review = rows["Under review"]
    assert (review["for_dto"], review["for_police"], review["for_dc"]) == (False, False, True)

    # A new status is offered to all three offices unless the admin says otherwise.
    everyone = admin_client.post("/api/admin/working-statuses", json={"name": "Awaiting reply"})
    assert everyone.json()["for_dto"] and everyone.json()["for_police"]
    police_only = admin_client.post(
        "/api/admin/working-statuses",
        json={"name": "Site visit done", "for_dto": False, "for_dc": False},
    )
    assert police_only.status_code == 201
    assert police_only.json()["for_police"] is True and police_only.json()["for_dc"] is False

    changed = admin_client.patch(
        f"/api/admin/working-statuses/{review['id']}", json={"for_police": True}
    )
    assert changed.json()["for_police"] is True and changed.json()["for_dc"] is True
    log = db.scalar(
        select(AuditLog)
        .where(AuditLog.action == "working_status.update")
        .order_by(AuditLog.id.desc())
    )
    assert log.old_value == {"for_police": False} and log.new_value == {"for_police": True}

    # A status that no office uses makes no sense: make it inactive instead.
    nobody = {"for_dto": False, "for_police": False, "for_dc": False}
    assert (
        admin_client.patch(f"/api/admin/working-statuses/{review['id']}", json=nobody)
    ).status_code == 400
    assert (
        admin_client.post("/api/admin/working-statuses", json={"name": "Unused", **nobody})
    ).status_code == 400


# -------------------------------------------------------- officer correction


def correction(db: Session, m: Masters, **changes) -> dict:
    changes.setdefault("documents", {})
    # The station that formkit.make_ready entered, so that it does not count as a change.
    changes.setdefault("destination_police_station_id", m.margherita.id)
    return {**OFFICER, "application": payload(db, m, **changes)}


def test_office_corrects_data_and_the_applicant_is_told_what_changed(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = new_application(client, db, m)
    user = as_office(client, db, login, application, Role.DTO)

    response = client.put(
        url(application),
        json=correction(db, m, seating_capacity=20, owner_name="Bipul Chandra Gogoi"),
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "PENDING_DTO"
    assert response.json()["form"]["seating_capacity"] == "20"

    row = db.scalar(select(AuditLog).where(AuditLog.action == "application.corrected_by_officer"))
    assert row.actor_user_id == user.id and row.officer_name == "A. Baruah"
    assert row.old_value == {"seating_capacity": 17, "owner_name": "Bipul Gogoi"}
    assert row.new_value == {"seating_capacity": 20, "owner_name": "Bipul Chandra Gogoi"}

    message = db.scalar(select(SmsLog).where(SmsLog.kind == "APPLICATION_CORRECTED"))
    assert "corrected by District Transport Office, Tinsukia" in message.message
    assert "Changed: seating capacity, owner's name." in message.message


def test_office_can_replace_a_document(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = new_application(client, db, m)
    as_office(client, db, login, application, Role.DTO)
    token = formkit.temp_upload(db, DocType.RC, formkit.image_bytes())
    db.commit()

    response = client.put(url(application), json=correction(db, m, documents={"RC": token}))

    assert response.status_code == 200, response.text
    rc = next(d for d in response.json()["documents"] if d["doc_type"] == "RC")
    assert rc["original_name"] == "RC.pdf" or rc["size_bytes"] == len(formkit.image_bytes())
    row = db.scalar(select(AuditLog).where(AuditLog.action == "application.corrected_by_officer"))
    assert row.new_value == {"documents_replaced": ["RC"]}


def test_correction_with_no_change_is_refused_and_form_rules_hold(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = new_application(client, db, m)
    as_office(client, db, login, application, Role.DTO)

    same = client.put(url(application), json=correction(db, m))
    assert same.status_code == 400 and "Nothing was changed" in same.json()["detail"]

    broken = client.put(url(application), json=correction(db, m, departure_time="05:00"))
    assert broken.status_code == 422 and "departure_time" in broken.json()["field_errors"]

    mobile = client.put(url(application), json=correction(db, m, leader_mobile=OTHER_MOBILE))
    assert mobile.status_code == 422 and "leader_mobile" in mobile.json()["field_errors"]


def test_only_the_holding_office_can_correct(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = at_stage(db, new_application(client, db, m), Status.PENDING_POLICE)
    as_office(client, db, login, application, Role.DTO)
    response = client.put(url(application), json=correction(db, m, owner_name="Someone Else"))
    assert response.status_code == 403


@pytest.mark.parametrize(
    "change", [{"vehicle_reg_number": "AS23Z9999"}, {"licence_number": "AS2399999999999"}]
)
@pytest.mark.parametrize(
    ("stage", "role"),
    [(Status.PENDING_POLICE, Role.POLICE_STATION), (Status.PENDING_DC, Role.DC_OFFICE)],
)
def test_vehicle_or_driver_changed_after_the_dto_stage_goes_back_to_the_dto(
    client: TestClient,
    db: Session,
    m: Masters,
    login: Login,
    stage: Status,
    role: Role,
    change: dict,
) -> None:
    application = at_stage(db, new_application(client, db, m), stage)
    as_office(client, db, login, application, role)

    response = client.put(url(application), json=correction(db, m, **change))

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "PENDING_DTO"
    assert response.json()["with_my_office"] is False
    row = db.scalar(select(AuditLog).where(AuditLog.action == "application.sent_back_to_dto"))
    assert row.new_value["remarks"] == "The vehicle or driver was changed."
    message = db.scalar(select(SmsLog).where(SmsLog.kind == "APPLICATION_CORRECTED"))
    assert "It is now with District Transport Office, Tinsukia." in message.message


def test_other_corrections_after_the_dto_stage_stay_with_the_office(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = at_stage(db, new_application(client, db, m), Status.PENDING_POLICE)
    as_office(client, db, login, application, Role.POLICE_STATION)
    response = client.put(
        url(application), json=correction(db, m, destination_police_station_id=m.digboi.id)
    )
    assert response.json()["status"] == "PENDING_POLICE"
    assert response.json()["destination_police_station"] == "Digboi PS"


@pytest.mark.parametrize(
    ("stage", "role"),
    [
        (Status.PENDING_DTO, Role.DTO),
        (Status.PENDING_POLICE, Role.POLICE_STATION),
        (Status.PENDING_DC, Role.DC_OFFICE),
    ],
)
def test_correcting_the_district_moves_the_application_to_the_new_districts_dto(
    client: TestClient, db: Session, m: Masters, login: Login, stage: Status, role: Role
) -> None:
    application = at_stage(db, new_application(client, db, m), stage)
    as_office(client, db, login, application, role)

    response = client.put(
        url(application),
        json=correction(
            db, m, origin_district_id=m.cachar.id, origin_police_station_id=m.silchar.id
        ),
    )

    assert response.status_code == 200, response.text
    db.refresh(application)
    assert application.status == Status.PENDING_DTO
    assert application.dto_office_id == m.dto_cachar.id
    assert application.origin_police_station_id == m.silchar.id
    # It has left the old district: the old office can no longer open it ...
    assert client.get(url(application)).status_code == 404
    # ... and the DTO of the new district has it in the queue.
    cachar_dto = office_user(db, application, Role.DTO)
    db.commit()
    client.post("/api/auth/logout")
    login(client, cachar_dto.user_id)
    queue = client.get("/api/officer/queue").json()
    assert [q["application_number"] for q in queue] == [application.application_number]

    message = db.scalar(select(SmsLog).where(SmsLog.kind == "APPLICATION_CORRECTED"))
    assert "It is now with District Transport Office, Cachar." in message.message


# ------------------------------------------------------- the state machine


def test_workflow_refuses_moves_it_does_not_know() -> None:
    allowed = {
        None: {Status.PENDING_DTO, Status.ON_HOLD_DUPLICATE_CLAIM},
        Status.ON_HOLD_DUPLICATE_CLAIM: {Status.PENDING_DTO, Status.REJECTED},
        Status.PENDING_DTO: {Status.PENDING_POLICE, Status.RETURNED_TO_APPLICANT, Status.REJECTED},
        Status.PENDING_POLICE: {
            Status.PENDING_DC,
            Status.RETURNED_TO_APPLICANT,
            Status.REJECTED,
            Status.PENDING_DTO,
        },
        Status.PENDING_DC: {
            Status.APPROVED,
            Status.RETURNED_TO_APPLICANT,
            Status.REJECTED,
            Status.PENDING_DTO,
        },
        Status.RETURNED_TO_APPLICANT: {*workflow.PENDING_STATUSES, Status.REJECTED},
    }
    assert {k: set(v) for k, v in workflow._ALLOWED.items()} == allowed


def test_workflow_itself_checks_the_office_not_only_the_api(
    client: TestClient, db: Session, m: Masters, make_user: MakeUser
) -> None:
    application = new_application(client, db, m)
    outsider = Acting(user=make_user(Role.DTO, dto_office=m.dto_cachar), name="X", designation="Y")
    for move in (
        lambda: workflow.forward(db, application, acting=outsider),
        lambda: workflow.reject(db, application, acting=outsider, reason="No"),
        lambda: workflow.return_to_applicant(db, application, acting=outsider, remarks="No"),
    ):
        with pytest.raises(DomainError):
            move()
    assert application.status == Status.PENDING_DTO


def test_acting_officer_must_give_name_and_designation(make_user: MakeUser, m: Masters) -> None:
    user = make_user(Role.DTO, dto_office=m.dto_tinsukia)
    with pytest.raises(DomainError, match="name and designation"):
        Acting(user=user, name=" ", designation="MVI")


# -------------------------------------------------------------- admin lists


def test_admin_maintains_working_statuses_and_reasons(
    admin_client: TestClient, db: Session
) -> None:
    statuses = admin_client.get("/api/admin/working-statuses").json()
    assert [s["name"] for s in statuses] == [
        "Document verification in progress",
        "Awaiting documents from applicant",
        "Inspection scheduled",
        "Inspection completed",
        "Verification in progress",
        "Field verification scheduled",
        "Under review",
        "Put up for approval",
    ]
    created = admin_client.post("/api/admin/working-statuses", json={"name": " Site  visit done "})
    assert created.status_code == 201 and created.json()["name"] == "Site visit done"
    assert (
        admin_client.post("/api/admin/working-statuses", json={"name": "site visit done"})
    ).status_code == 409
    # "Received" is built in, so it cannot be added as a row.
    assert (
        admin_client.post("/api/admin/working-statuses", json={"name": "Received"})
    ).status_code == 409
    renamed = admin_client.patch(
        f"/api/admin/working-statuses/{created.json()['id']}",
        json={"name": "Site visit completed", "is_active": False},
    )
    assert renamed.json() == {
        "id": created.json()["id"],
        "name": "Site visit completed",
        "is_active": False,
        "for_dto": True,
        "for_police": True,
        "for_dc": True,
    }

    reasons = admin_client.get("/api/admin/remark-reasons").json()
    assert sum(r["kind"] == "RETURN" for r in reasons) == 8
    assert sum(r["kind"] == "REJECT" for r in reasons) == 11
    added = admin_client.post(
        "/api/admin/remark-reasons", json={"kind": "RETURN", "name": "Photo too dark"}
    )
    assert added.status_code == 201
    assert (
        admin_client.post("/api/admin/remark-reasons", json={"kind": "MAYBE", "name": "x"})
    ).status_code == 422
    assert admin_client.delete(f"/api/admin/remark-reasons/{added.json()['id']}").status_code == 204


def test_working_status_in_use_cannot_be_deleted(
    admin_client: TestClient, anonymous: TestClient, db: Session, m: Masters
) -> None:
    application = new_application(anonymous, db, m)
    in_use = db.scalar(select(WorkingStatus).where(WorkingStatus.name == "Under review"))
    application.working_status_id = in_use.id
    db.commit()
    assert admin_client.delete(f"/api/admin/working-statuses/{in_use.id}").status_code == 409
    unused = db.scalar(select(WorkingStatus).where(WorkingStatus.name == "Put up for approval"))
    assert admin_client.delete(f"/api/admin/working-statuses/{unused.id}").status_code == 204
