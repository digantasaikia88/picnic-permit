"""What each office records before it forwards (PRD Sections 7.1 to 7.3),
duplicate claims and flagged mobile numbers (Section 10.1).
"""

import json
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutil import today_local
from app.models import (
    Application,
    AuditLog,
    DocType,
    FlaggedMobile,
    InspectionStatus,
    Role,
    SmsLog,
    Status,
    User,
)
from app.services import captcha, dto, uploads
from app.services import status as status_service
from tests import formkit
from tests.conftest import Login, MakeUser, Masters
from tests.formkit import OFFICER, PDF, day, payload, submit, temp_upload
from tests.test_officer import as_office, url

OTHER_MOBILE = "9876511111"
THIRD_MOBILE = "9876522222"

ALL_OK = {key: "OK" for key in dto.CHECKLIST}


def fresh(client: TestClient, db: Session, m: Masters, **changes) -> Application:
    """A newly submitted application.

    The DTO's findings and document check are filled in, so that a test can look
    at one rule at a time. Pass `checks=False` for an application with nothing
    recorded by any office.
    """
    checks = changes.pop("checks", True)
    raise_claim = changes.pop("raise_claim", False)
    response = submit(client, db, payload(db, m, **changes), raise_claim=raise_claim)
    assert response.status_code == 201, response.text
    number = response.json()["application_number"]
    application = db.scalar(select(Application).where(Application.application_number == number))
    return formkit.complete_dto_checks(db, application) if checks else application


def with_certificate(db: Session) -> dict[str, str]:
    """The required documents and an inspection certificate."""
    types = [*formkit.REQUIRED_DOCUMENTS, DocType.INSPECTION_CERTIFICATE]
    return {doc.value: temp_upload(db, doc) for doc in types}


def certificate_of(application: Application) -> int:
    return next(d.id for d in application.documents if d.doc_type == DocType.INSPECTION_CERTIFICATE)


def passed(client: TestClient, application: Application) -> None:
    response = client.post(
        url(application, "inspection/result"),
        json={
            **OFFICER,
            "checklist": ALL_OK,
            "inspected_on": today_local().isoformat(),
            "inspecting_officer": "P. Saikia, MVI",
            "passed": True,
        },
    )
    assert response.status_code == 200, response.text


def last_audit(db: Session, action: str) -> AuditLog:
    return db.scalar(
        select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id.desc()).limit(1)
    )


def last_sms(db: Session, kind: str) -> SmsLog:
    return db.scalar(select(SmsLog).where(SmsLog.kind == kind).order_by(SmsLog.id.desc()).limit(1))


# ------------------------------------------------------- DTO: forward gate


def test_dto_cannot_forward_until_the_inspection_is_passed_or_a_certificate_confirmed(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = fresh(client, db, m)
    as_office(client, db, login, application, Role.DTO)

    detail = client.get(url(application)).json()
    assert detail["inspection_status"] == "INSPECTION_REQUIRED"
    assert "inspection" in detail["forward_blockers"][0]

    refused = client.post(url(application, "forward"), json=OFFICER)
    assert refused.status_code == 400
    assert "inspection" in refused.json()["detail"]
    db.refresh(application)
    assert application.status == Status.PENDING_DTO

    passed(client, application)
    assert client.get(url(application)).json()["forward_blockers"] == []
    assert client.post(url(application, "forward"), json=OFFICER).json()["status"] == (
        "PENDING_POLICE"
    )


def test_an_uploaded_certificate_alone_is_not_enough_the_dto_must_confirm_it(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = fresh(client, db, m, documents=with_certificate(db))
    assert application.inspection_status == InspectionStatus.CERTIFICATE_UPLOADED
    as_office(client, db, login, application, Role.DTO)
    assert client.post(url(application, "forward"), json=OFFICER).status_code == 400

    confirmed = client.post(
        url(application, "inspection/confirm-certificate"),
        json={**OFFICER, "document_id": certificate_of(application)},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["certificate_confirmed"] is True
    assert confirmed.json()["forward_blockers"] == []
    entry = last_audit(db, "application.certificate_confirmed")
    assert entry.new_value == {"confirmed_certificate_of": application.application_number}
    assert entry.officer_name == OFFICER["officer_name"]

    assert client.post(url(application, "forward"), json=OFFICER).json()["status"] == (
        "PENDING_POLICE"
    )


def test_a_replaced_certificate_has_to_be_confirmed_again(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = fresh(client, db, m, documents=with_certificate(db))
    as_office(client, db, login, application, Role.DTO)
    client.post(
        url(application, "inspection/confirm-certificate"),
        json={**OFFICER, "document_id": certificate_of(application)},
    )

    # The applicant uploads another file from the status page.
    upload = uploads.save_temp(
        db, filename="new.pdf", content=PDF, doc_type=DocType.INSPECTION_CERTIFICATE
    )
    status_service.upload_inspection_certificate(db, application, upload)
    db.commit()

    detail = client.get(url(application)).json()
    assert detail["certificate_confirmed"] is False
    assert client.post(url(application, "forward"), json=OFFICER).status_code == 400


def test_dto_can_take_a_confirmation_back(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = fresh(client, db, m, documents=with_certificate(db))
    as_office(client, db, login, application, Role.DTO)
    path = url(application, "inspection/confirm-certificate")
    client.post(path, json={**OFFICER, "document_id": certificate_of(application)})

    undone = client.post(path, json={**OFFICER, "document_id": None})
    assert undone.json()["certificate_confirmed"] is False


def test_certificate_on_record_for_the_same_vehicle_is_shown_and_can_be_confirmed(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    earlier = fresh(client, db, m, documents=with_certificate(db))
    later = fresh(client, db, m, travel_date=day(20).isoformat())
    other_vehicle = fresh(
        client,
        db,
        m,
        travel_date=day(21).isoformat(),
        vehicle_reg_number="AS 23 ZZ 0001",
        documents=with_certificate(db),
    )
    as_office(client, db, login, later, Role.DTO)

    detail = client.get(url(later)).json()
    assert [c["application_number"] for c in detail["earlier_certificates"]] == [
        earlier.application_number
    ]
    document_id = detail["earlier_certificates"][0]["document_id"]
    assert client.get(url(later, f"certificates/{document_id}")).status_code == 200

    # A certificate of another vehicle cannot be opened or confirmed from here.
    foreign = certificate_of(other_vehicle)
    assert client.get(url(later, f"certificates/{foreign}")).status_code == 404
    path = url(later, "inspection/confirm-certificate")
    assert client.post(path, json={**OFFICER, "document_id": foreign}).status_code == 404

    confirmed = client.post(path, json={**OFFICER, "document_id": document_id})
    assert confirmed.json()["certificate_confirmed"] is True
    assert client.post(url(later, "forward"), json=OFFICER).json()["status"] == "PENDING_POLICE"


def send_result_with_certificate(client: TestClient, application: Application, **changes):
    body = {
        **OFFICER,
        "checklist": dict(ALL_OK),
        "inspected_on": today_local().isoformat(),
        "inspecting_officer": "P. Saikia, MVI",
        "passed": True,
        "remarks": "",
    }
    body.update(changes)
    return client.post(
        url(application, "inspection/result-with-certificate"),
        data={"data": json.dumps(body)},
        files={"file": ("issued-certificate.pdf", PDF, "application/pdf")},
    )


def test_certificate_issued_after_inspection_is_uploaded_with_the_result(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    # The applicant had uploaded a certificate of their own.
    application = fresh(client, db, m, documents=with_certificate(db))
    as_office(client, db, login, application, Role.DTO)

    saved = send_result_with_certificate(client, application)
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["inspection_status"] == "PASSED"
    assert body["inspection"]["inspecting_officer"] == "P. Saikia, MVI"
    # The scan takes the place of the applicant's file in the documents.
    certificates = [d for d in body["documents"] if d["doc_type"] == "INSPECTION_CERTIFICATE"]
    assert [d["original_name"] for d in certificates] == ["issued-certificate.pdf"]
    assert body["confirmed_certificate_id"] == certificates[0]["id"]
    assert body["forward_blockers"] == []

    # One SMS, with the result. Both steps are in the timeline.
    assert "PASSED inspection" in last_sms(db, "INSPECTION_RESULT").message
    assert last_sms(db, "APPLICATION_CORRECTED") is None
    assert last_audit(db, "application.inspection_recorded") is not None
    uploaded = last_audit(db, "application.inspection_certificate_uploaded_by_office")
    assert uploaded.new_value["file"] == "issued-certificate.pdf"


def test_result_with_certificate_keeps_the_rules_of_the_result(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = fresh(client, db, m)
    as_office(client, db, login, application, Role.DTO)

    # No certificate for a vehicle that failed.
    failed = send_result_with_certificate(
        client, application, passed=False, checklist={**ALL_OK, "brakes": "NOT_OK"}
    )
    assert failed.status_code == 400
    # The checklist rules hold, and nothing is saved when they fail.
    bad = send_result_with_certificate(client, application, checklist={**ALL_OK, "horn": "NOT_OK"})
    assert bad.status_code == 400
    assert (
        send_result_with_certificate(client, application, inspecting_officer="").status_code == 400
    )
    db.refresh(application)
    assert application.inspection_status == InspectionStatus.INSPECTION_REQUIRED
    assert all(d.doc_type != DocType.INSPECTION_CERTIFICATE for d in application.documents)

    # The name and designation may also come as fields of the form.
    form_fields = client.post(
        url(application, "inspection/result-with-certificate"),
        data={
            "data": json.dumps(
                {
                    "checklist": ALL_OK,
                    "inspected_on": today_local().isoformat(),
                    "inspecting_officer": "MVI",
                    "passed": True,
                }
            ),
            **OFFICER,
        },
        files={"file": ("wrong.txt", b"not a document", "text/plain")},
    )
    # A wrong kind of file is refused, and the result is not saved either.
    assert form_fields.status_code == 400
    db.refresh(application)
    assert application.inspection_status == InspectionStatus.INSPECTION_REQUIRED

    as_office(client, db, login, application, Role.POLICE_STATION)
    assert send_result_with_certificate(client, application).status_code == 403


def test_certificate_can_be_added_later_to_a_result_already_recorded(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = fresh(client, db, m)
    as_office(client, db, login, application, Role.DTO)
    passed(client, application)

    body = send_result_with_certificate(client, application).json()
    assert body["inspection_status"] == "PASSED"
    assert [
        d["original_name"] for d in body["documents"] if d["doc_type"] == "INSPECTION_CERTIFICATE"
    ] == ["issued-certificate.pdf"]


def test_dto_cannot_forward_until_its_findings_and_document_check_are_complete(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = fresh(client, db, m, checks=False)
    as_office(client, db, login, application, Role.DTO)
    passed(client, application)

    def blockers() -> list[str]:
        return client.get(url(application)).json()["forward_blockers"]

    def forward() -> int:
        return client.post(url(application, "forward"), json=OFFICER).status_code

    # Nothing recorded: the findings and the documents are both missing.
    first = client.post(url(application, "forward"), json=OFFICER)
    assert first.status_code == 400
    assert len(first.json()["errors"]) == 2
    assert "findings" in blockers()[0] and "5 document(s)" in blockers()[1]

    # Findings with an item left "not checked", and no challan numbers.
    partial = {key: "YES" for key in dto.VAHAN_ITEMS if key != "permit"}
    client.post(
        url(application, "dto-findings"),
        json=findings(vahan=partial, challans_unpaid=None, challans_on_record=None),
    )
    assert "Not checked: Permit." in blockers()[0]
    assert "challans" in blockers()[1]
    assert forward() == 400

    # A "No" is an answer: it does not block. The DTO decides.
    client.post(
        url(application, "dto-findings"),
        json=findings(vahan={**{key: "YES" for key in dto.VAHAN_ITEMS}, "insurance": "NO"}),
    )
    assert blockers() == [
        "Check 5 document(s) against the originals and mark each as verified or not verified."
    ]

    # Every document has to be marked; "not verified" is a mark too.
    documents = client.get(url(application)).json()["documents"]
    for index, document in enumerate(documents[:-1]):
        client.post(
            url(application, f"documents/{document['id']}/verify"),
            json={**OFFICER, "verified": index != 0},
        )
        assert f"{len(documents) - index - 1} document(s)" in blockers()[0]
    assert forward() == 400
    client.post(
        url(application, f"documents/{documents[-1]['id']}/verify"),
        json={**OFFICER, "verified": True},
    )
    assert blockers() == []
    assert forward() == 200
    db.refresh(application)
    assert application.status == Status.PENDING_POLICE


def test_a_replaced_document_has_to_be_checked_again(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = fresh(client, db, m)
    as_office(client, db, login, application, Role.DTO)
    passed(client, application)
    assert client.get(url(application)).json()["forward_blockers"] == []

    replaced = client.put(
        url(application),
        json={
            **OFFICER,
            "application": payload(db, m, documents={"RC": temp_upload(db, DocType.RC)}),
        },
    )
    assert replaced.status_code == 200, replaced.text
    assert "1 document(s)" in replaced.json()["forward_blockers"][0]


def test_the_inspection_certificate_needs_no_separate_document_mark(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = fresh(client, db, m)
    as_office(client, db, login, application, Role.DTO)
    saved = send_result_with_certificate(client, application)
    assert saved.json()["forward_blockers"] == []


# -------------------------------------------------------- DTO: findings


def findings(**changes) -> dict:
    body = {
        **OFFICER,
        "vahan": {key: "YES" for key in dto.VAHAN_ITEMS},
        "vahan_remarks": "Matches the RC",
        "challans_unpaid": 0,
        "challans_on_record": 2,
        "challan_remarks": "",
        "sarathi": {key: "YES" for key in dto.SARATHI_ITEMS},
        "sarathi_remarks": "",
    }
    body.update(changes)
    return body


def test_dto_records_vahan_challan_and_sarathi_findings(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = fresh(client, db, m, checks=False)
    as_office(client, db, login, application, Role.DTO)

    saved = client.post(
        url(application, "dto-findings"),
        json=findings(vahan={"rc": "YES", "insurance": "NO"}),
    )
    assert saved.status_code == 200, saved.text
    recorded = saved.json()["dto_findings"]
    assert recorded["vahan"]["insurance"] == "NO"
    # An item left out is "not checked".
    assert recorded["vahan"]["permit"] == "NOT_CHECKED"
    assert recorded["challans_on_record"] == 2
    assert saved.json()["challan_warning"] is False

    entry = last_audit(db, "application.dto_findings")
    assert entry.new_value["vahan.insurance"] == "NO"
    assert entry.officer_designation == OFFICER["officer_designation"]

    # Saving again logs only what changed.
    client.post(
        url(application, "dto-findings"),
        json=findings(vahan={"rc": "YES", "insurance": "YES"}),
    )
    again = last_audit(db, "application.dto_findings")
    assert again.old_value == {"vahan.insurance": "NO"}
    assert again.new_value == {"vahan.insurance": "YES"}


def test_three_or_more_unpaid_challans_warn_but_do_not_block(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = fresh(client, db, m)
    as_office(client, db, login, application, Role.DTO)
    saved = client.post(
        url(application, "dto-findings"), json=findings(challans_unpaid=3, challans_on_record=5)
    )
    assert saved.json()["challan_warning"] is True

    passed(client, application)
    assert client.post(url(application, "forward"), json=OFFICER).status_code == 200


def test_findings_are_checked(client: TestClient, db: Session, m: Masters, login: Login) -> None:
    application = fresh(client, db, m)
    as_office(client, db, login, application, Role.DTO)
    path = url(application, "dto-findings")

    more_unpaid = client.post(path, json=findings(challans_unpaid=4, challans_on_record=1))
    assert more_unpaid.status_code == 400
    assert client.post(path, json=findings(vahan={"rc": "MAYBE"})).status_code == 400
    assert client.post(path, json=findings(vahan={"engine": "YES"})).status_code == 400
    assert client.post(path, json=findings(challans_unpaid=-1)).status_code == 422


def test_only_the_dto_that_holds_the_application_records_dto_work(
    client: TestClient, db: Session, m: Masters, login: Login, make_user: MakeUser
) -> None:
    application = fresh(client, db, m)
    calls = [
        ("dto-findings", findings()),
        ("inspection/schedule", {**OFFICER, "on": day(2).isoformat(), "at": "10:00", "place": "X"}),
        (
            "inspection/result",
            {
                **OFFICER,
                "checklist": ALL_OK,
                "inspected_on": today_local().isoformat(),
                "inspecting_officer": "MVI",
                "passed": True,
            },
        ),
        ("inspection/confirm-certificate", {**OFFICER, "document_id": None}),
    ]

    # The police station of the application sees it but does not hold it.
    as_office(client, db, login, application, Role.POLICE_STATION)
    for action, body in calls:
        assert client.post(url(application, action), json=body).status_code == 403, action

    # The DTO of another district does not see it at all.
    outsider = make_user(Role.DTO, dto_office=m.dto_cachar)
    client.post("/api/auth/logout")
    login(client, outsider.user_id)
    for action, body in calls:
        assert client.post(url(application, action), json=body).status_code == 404, action

    # Once forwarded, the police station holds it, but this is still the DTO's work.
    formkit.make_ready(db, application)
    as_office(client, db, login, application, Role.DTO)
    client.post(url(application, "forward"), json=OFFICER)
    as_office(client, db, login, application, Role.POLICE_STATION)
    for action, body in calls:
        assert client.post(url(application, action), json=body).status_code == 400, action


def test_dto_marks_each_document_as_checked_against_the_original(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = fresh(client, db, m, checks=False)
    as_office(client, db, login, application, Role.DTO)
    documents = client.get(url(application)).json()["documents"]
    assert all(d["verified"] is None for d in documents)
    rc = next(d for d in documents if d["doc_type"] == "RC")

    marked = client.post(
        url(application, f"documents/{rc['id']}/verify"), json={**OFFICER, "verified": True}
    )
    assert marked.status_code == 200, marked.text
    after = {d["doc_type"]: d["verified"] for d in marked.json()["documents"]}
    assert after["RC"] is True and after["INSURANCE"] is None
    assert last_audit(db, "application.document_verified").new_value == {"verified.RC": True}

    not_ok = client.post(
        url(application, f"documents/{rc['id']}/verify"), json={**OFFICER, "verified": False}
    )
    assert {d["doc_type"]: d["verified"] for d in not_ok.json()["documents"]}["RC"] is False

    missing = client.post(
        url(application, "documents/999999/verify"), json={**OFFICER, "verified": True}
    )
    assert missing.status_code == 404


# ------------------------------------------------------ DTO: inspection


def test_dto_schedules_the_inspection_and_the_applicant_is_told(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = fresh(client, db, m)
    as_office(client, db, login, application, Role.DTO)
    when = day(3)

    scheduled = client.post(
        url(application, "inspection/schedule"),
        json={**OFFICER, "on": when.isoformat(), "at": "10:30", "place": "DTO office, Tinsukia"},
    )
    assert scheduled.status_code == 200, scheduled.text
    assert scheduled.json()["inspection_status"] == "INSPECTION_SCHEDULED"
    assert scheduled.json()["inspection"]["place"] == "DTO office, Tinsukia"

    message = last_sms(db, "INSPECTION_SCHEDULED").message
    assert when.strftime("%d-%m-%Y") in message
    assert "10:30 AM" in message and "DTO office, Tinsukia" in message
    assert application.vehicle_reg_number in message
    assert last_audit(db, "application.inspection_scheduled").new_value["inspection_status"] == (
        "INSPECTION_SCHEDULED"
    )
    # Scheduling is not passing.
    assert client.post(url(application, "forward"), json=OFFICER).status_code == 400


def test_inspection_date_must_be_from_today_to_the_travel_date(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = fresh(client, db, m)
    as_office(client, db, login, application, Role.DTO)

    def schedule(on) -> int:
        body = {**OFFICER, "on": on.isoformat(), "at": "10:00", "place": "DTO office"}
        return client.post(url(application, "inspection/schedule"), json=body).status_code

    assert schedule(today_local() - timedelta(days=1)) == 400
    assert schedule(application.travel_date + timedelta(days=1)) == 400
    assert schedule(today_local()) == 200
    assert schedule(application.travel_date) == 200


def result(**changes) -> dict:
    body = {
        **OFFICER,
        "checklist": dict(ALL_OK),
        "inspected_on": today_local().isoformat(),
        "inspecting_officer": "P. Saikia, MVI",
        "passed": True,
        "remarks": "",
    }
    body.update(changes)
    return body


def test_inspection_result_needs_the_whole_checklist(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = fresh(client, db, m)
    as_office(client, db, login, application, Role.DTO)
    path = url(application, "inspection/result")

    partial = {key: "OK" for key in list(dto.CHECKLIST)[:-1]}
    missing = client.post(path, json=result(checklist=partial))
    assert missing.status_code == 400
    assert "Speed Limiting Device" in missing.json()["detail"]

    bad_brakes = {**ALL_OK, "brakes": "NOT_OK"}
    cannot_pass = client.post(path, json=result(checklist=bad_brakes))
    assert cannot_pass.status_code == 400
    assert "Brakes" in cannot_pass.json()["detail"]

    tomorrow = (today_local() + timedelta(days=1)).isoformat()
    assert client.post(path, json=result(inspected_on=tomorrow)).status_code == 400
    assert client.post(path, json=result(passed=False)).status_code == 400

    # A device that does not apply to the vehicle does not stop it passing.
    no_sld = {**ALL_OK, "sld": "NOT_APPLICABLE"}
    assert client.post(path, json=result(checklist=no_sld)).status_code == 200


def test_a_passed_inspection_lets_the_dto_forward_and_tells_the_applicant(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = fresh(client, db, m)
    as_office(client, db, login, application, Role.DTO)

    saved = client.post(url(application, "inspection/result"), json=result())
    assert saved.json()["inspection_status"] == "PASSED"
    assert saved.json()["inspection"]["inspecting_officer"] == "P. Saikia, MVI"
    assert "PASSED inspection" in last_sms(db, "INSPECTION_RESULT").message
    assert saved.json()["forward_blockers"] == []

    # A vehicle that has passed is not scheduled again.
    again = client.post(
        url(application, "inspection/schedule"),
        json={**OFFICER, "on": day(2).isoformat(), "at": "10:00", "place": "DTO office"},
    )
    assert again.status_code == 400


def test_a_failed_inspection_blocks_forwarding_until_a_new_one_passes(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = fresh(client, db, m)
    as_office(client, db, login, application, Role.DTO)

    failed = client.post(
        url(application, "inspection/result"),
        json=result(passed=False, checklist={**ALL_OK, "tyres": "NOT_OK"}),
    )
    assert failed.json()["inspection_status"] == "FAILED"
    message = last_sms(db, "INSPECTION_RESULT").message
    assert "did NOT pass" in message and "tyres" in message
    assert client.post(url(application, "forward"), json=OFFICER).status_code == 400

    # The DTO may return or reject it (Section 7.1), or inspect it again.
    rescheduled = client.post(
        url(application, "inspection/schedule"),
        json={**OFFICER, "on": day(2).isoformat(), "at": "11:00", "place": "DTO office"},
    )
    assert rescheduled.json()["inspection_status"] == "INSPECTION_SCHEDULED"
    assert "checklist" not in rescheduled.json()["inspection"]
    passed(client, application)
    assert client.post(url(application, "forward"), json=OFFICER).status_code == 200


def test_changing_the_vehicle_clears_the_inspection_and_the_findings(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = fresh(client, db, m)
    as_office(client, db, login, application, Role.DTO)
    client.post(url(application, "dto-findings"), json=findings())
    passed(client, application)

    corrected = client.put(
        url(application),
        json={
            **OFFICER,
            "application": payload(db, m, vehicle_reg_number="AS 23 ZZ 0002", documents={}),
        },
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["inspection_status"] == "INSPECTION_REQUIRED"
    assert corrected.json()["dto_findings"] is None
    assert corrected.json()["forward_blockers"] != []


# ------------------------------------------------------------- police


def police_record(m: Masters, **changes) -> dict:
    body = {
        **OFFICER,
        "destination_police_station_id": m.digboi.id,
        "driving_band": "UP_TO_60",
        "verification_remarks": "Group verified at the address.",
        "checkpoints": "Makum bypass",
        "comments": "No concern.",
    }
    body.update(changes)
    return body


def at_police(client: TestClient, db: Session, m: Masters, login: Login, **changes) -> Application:
    application = fresh(client, db, m, **changes)
    as_office(client, db, login, application, Role.DTO)
    passed(client, application)
    assert client.post(url(application, "forward"), json=OFFICER).status_code == 200
    as_office(client, db, login, application, Role.POLICE_STATION)
    return application


def test_police_cannot_forward_until_the_destination_police_station_is_entered(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = at_police(client, db, m, login)

    refused = client.post(url(application, "forward"), json=OFFICER)
    assert refused.status_code == 400
    assert "destination police station" in refused.json()["detail"]

    saved = client.post(url(application, "police-record"), json=police_record(m))
    assert saved.status_code == 200, saved.text
    assert saved.json()["destination_police_station"] == "Digboi PS"
    assert saved.json()["police_findings"]["checkpoints"] == "Makum bypass"
    assert saved.json()["forward_blockers"] == []
    entry = last_audit(db, "application.police_record")
    assert entry.new_value["destination_police_station"] == "Digboi PS"
    assert entry.new_value["driving_time_confirmed"] is True

    assert client.post(url(application, "forward"), json=OFFICER).json()["status"] == "PENDING_DC"


def test_police_must_save_its_verification_even_when_the_destination_station_is_given(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    # The applicant had already named the destination police station in the form.
    application = at_police(client, db, m, login, destination_police_station_id=m.digboi.id)
    refused = client.post(url(application, "forward"), json=OFFICER)
    assert refused.status_code == 400
    assert "police verification" in refused.json()["detail"]

    no_remarks = client.post(
        url(application, "police-record"), json=police_record(m, verification_remarks=" ")
    )
    assert no_remarks.status_code == 400
    assert client.post(url(application, "forward"), json=OFFICER).status_code == 400

    client.post(url(application, "police-record"), json=police_record(m))
    assert client.post(url(application, "forward"), json=OFFICER).json()["status"] == "PENDING_DC"


def test_destination_police_station_must_be_of_the_destination_district(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = at_police(client, db, m, login)
    wrong = client.post(
        url(application, "police-record"),
        json=police_record(m, destination_police_station_id=m.silchar.id),
    )
    assert wrong.status_code == 400
    assert "Tinsukia" in wrong.json()["detail"]


def test_police_can_correct_the_driving_time_to_the_other_band(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = at_police(client, db, m, login)
    assert application.needs_dc_specific_approval is False

    saved = client.post(
        url(application, "police-record"), json=police_record(m, driving_band="FROM_60_TO_90")
    )
    assert saved.json()["needs_dc_specific_approval"] is True
    entry = last_audit(db, "application.police_record")
    assert entry.old_value["driving_band"] == "Up to 60 minutes"
    assert entry.new_value["driving_band"] == "60 to 90 minutes"
    # The applicant is told that the data of the application was changed.
    assert "driving time" in last_sms(db, "APPLICATION_CORRECTED").message

    back = client.post(url(application, "police-record"), json=police_record(m))
    assert back.json()["needs_dc_specific_approval"] is False


def test_only_the_police_station_that_holds_it_records_police_work(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = fresh(client, db, m)
    as_office(client, db, login, application, Role.DTO)
    # At the DTO stage this is not the DTO's to record.
    assert client.post(url(application, "police-record"), json=police_record(m)).status_code == 400
    as_office(client, db, login, application, Role.POLICE_STATION)
    assert client.post(url(application, "police-record"), json=police_record(m)).status_code == 403


def test_police_station_transfers_to_another_station_of_the_same_district(
    client: TestClient, db: Session, m: Masters, login: Login, make_user: MakeUser
) -> None:
    application = at_police(client, db, m, login)
    digboi_user = make_user(Role.POLICE_STATION, police_station=m.digboi)

    moved = client.post(
        url(application, "transfer"),
        json={**OFFICER, "police_station_id": m.digboi.id, "remarks": "Address is under Digboi."},
    )
    assert moved.status_code == 200, moved.text
    db.refresh(application)
    assert application.status == Status.PENDING_POLICE
    assert application.origin_police_station_id == m.digboi.id

    entry = last_audit(db, "application.transferred")
    assert entry.old_value == {"origin_police_station": "Margherita PS"}
    assert entry.new_value == {
        "origin_police_station": "Digboi PS",
        "remarks": "Address is under Digboi.",
    }
    message = last_sms(db, "APPLICATION_TRANSFERRED").message
    assert "Margherita PS" in message and "Digboi PS" in message

    # It has left the first station altogether, and is in the queue of the second.
    assert client.get(url(application)).status_code == 404
    assert client.get("/api/officer/queue").json() == []
    client.post("/api/auth/logout")
    login(client, digboi_user.user_id)
    queue = client.get("/api/officer/queue").json()
    assert [item["application_number"] for item in queue] == [application.application_number]
    # The receiving station can transfer again, and the log shows every transfer.
    back = client.post(
        url(application, "transfer"),
        json={**OFFICER, "police_station_id": m.margherita.id, "remarks": "Sent back."},
    )
    assert back.status_code == 200
    transfers = db.scalars(select(AuditLog).where(AuditLog.action == "application.transferred"))
    assert len(list(transfers)) == 2


def test_transfer_rules(client: TestClient, db: Session, m: Masters, login: Login) -> None:
    application = at_police(client, db, m, login)
    path = url(application, "transfer")

    def transfer(station_id: int, remarks: str = "Wrong station") -> int:
        body = {**OFFICER, "police_station_id": station_id, "remarks": remarks}
        return client.post(path, json=body).status_code

    assert transfer(m.silchar.id) == 400  # another district
    assert transfer(m.margherita.id) == 400  # the same station
    assert transfer(m.digboi.id, remarks="") == 422  # the remark is mandatory
    assert transfer(999999) == 404

    m.digboi.is_active = False
    db.commit()
    assert transfer(m.digboi.id) == 400


def test_only_a_police_station_transfers(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = fresh(client, db, m)
    as_office(client, db, login, application, Role.DTO)
    body = {**OFFICER, "police_station_id": m.digboi.id, "remarks": "Wrong station"}
    assert client.post(url(application, "transfer"), json=body).status_code == 400


# ----------------------------------------------------------------- DC


def test_dc_must_give_a_specific_approval_remark_for_60_to_90_minutes(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = at_police(client, db, m, login, driving_band="FROM_60_TO_90")
    client.post(
        url(application, "police-record"), json=police_record(m, driving_band="FROM_60_TO_90")
    )
    client.post(url(application, "forward"), json=OFFICER)
    as_office(client, db, login, application, Role.DC_OFFICE)

    refused = client.post(url(application, "forward"), json=OFFICER)
    assert refused.status_code == 400
    assert "specific approval" in refused.json()["detail"]

    approved = client.post(
        url(application, "forward"),
        json={**OFFICER, "specific_approval_remark": "Road is good; allowed up to 80 minutes."},
    )
    assert approved.json()["status"] == "APPROVED"
    assert approved.json()["dc_specific_approval_remark"] == (
        "Road is good; allowed up to 80 minutes."
    )
    assert "Specific approval" in last_audit(db, "application.approved").new_value["remarks"]


def test_dc_needs_no_specific_remark_for_up_to_60_minutes(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = at_police(client, db, m, login)
    client.post(url(application, "police-record"), json=police_record(m))
    client.post(url(application, "forward"), json=OFFICER)
    as_office(client, db, login, application, Role.DC_OFFICE)
    assert client.post(url(application, "forward"), json=OFFICER).json()["status"] == "APPROVED"


# ----------------------------------------------------- duplicate claims


def claim_pair(client: TestClient, db: Session, m: Masters, **first) -> tuple:
    """An application, and a claim raised against it by another mobile number."""
    original = fresh(client, db, m, **first)
    claim = fresh(
        client, db, m, leader_mobile=OTHER_MOBILE, leader_name="Genuine Owner", raise_claim=True
    )
    assert claim.status == Status.ON_HOLD_DUPLICATE_CLAIM
    return original, claim


def as_dto_of(client: TestClient, db: Session, login: Login, application: Application) -> User:
    return as_office(client, db, login, application, Role.DTO)


def test_dto_sees_the_claim_and_what_blocks_it_side_by_side(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    original, claim = claim_pair(client, db, m)
    as_dto_of(client, db, login, claim)

    assert client.get("/api/officer/reference").json()["duplicate_claims"] == 1
    listed = client.get("/api/officer/claims").json()
    assert len(listed) == 1
    pair = listed[0]
    assert pair["claim"]["application_number"] == claim.application_number
    assert pair["claim"]["leader_mobile"] == OTHER_MOBILE
    other = pair["blocking"][0]
    assert other["application_number"] == original.application_number
    assert other["same_vehicle"] is True and other["same_driver"] is True
    assert other["owner_name"] == original.owner_name
    assert {d["doc_type"] for d in other["documents"]} >= {"RC", "OWNER_SELF_CERTIFICATE"}

    # The documents of both can be opened for the comparison.
    own = pair["claim"]["documents"][0]["id"]
    theirs = other["documents"][0]["id"]
    base = f"/api/officer/claims/{claim.id}"
    assert client.get(f"{base}/documents/{own}").status_code == 200
    assert client.get(f"{base}/others/{original.id}/documents/{theirs}").status_code == 200
    assert client.get(f"{base}/others/{original.id}/documents/{own}").status_code == 404

    # A claim on hold is not in the work queue: it is in the claims list.
    queue = [item["application_number"] for item in client.get("/api/officer/queue").json()]
    assert queue == [original.application_number]


def test_claims_are_for_the_dto_of_the_claims_district_only(
    client: TestClient, db: Session, m: Masters, login: Login, make_user: MakeUser
) -> None:
    _original, claim = claim_pair(client, db, m)
    body = {**OFFICER, "remarks": ""}

    as_office(client, db, login, claim, Role.POLICE_STATION)
    assert client.get("/api/officer/claims").status_code == 403
    assert client.post(f"/api/officer/claims/{claim.id}/accept", json=body).status_code == 403

    outsider = make_user(Role.DTO, dto_office=m.dto_cachar)
    client.post("/api/auth/logout")
    login(client, outsider.user_id)
    assert client.get("/api/officer/claims").json() == []
    assert client.get(f"/api/officer/claims/{claim.id}").status_code == 404
    assert client.post(f"/api/officer/claims/{claim.id}/accept", json=body).status_code == 404
    assert client.post(f"/api/officer/claims/{claim.id}/reject", json=body).status_code == 404


def test_accepting_a_claim_rejects_the_other_application_and_takes_the_claim_up(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    original, claim = claim_pair(client, db, m)
    as_dto_of(client, db, login, claim)

    accepted = client.post(
        f"/api/officer/claims/{claim.id}/accept",
        json={**OFFICER, "remarks": "Owner confirmed by phone.", "flag_mobiles": True},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "PENDING_DTO"
    assert accepted.json()["with_my_office"] is True

    db.refresh(original)
    assert original.status == Status.REJECTED
    assert original.status_remarks == (
        "Not authorised by the vehicle owner or driver. Owner confirmed by phone."
    )
    # Both applicants are told.
    assert last_sms(db, "APPLICATION_REJECTED").mobile == original.leader_mobile
    assert last_sms(db, "DUPLICATE_CLAIM_ACCEPTED").mobile == OTHER_MOBILE
    assert last_audit(db, "application.claim_accepted").officer_name == OFFICER["officer_name"]

    # The number that filed the other application is flagged.
    flagged = db.scalar(select(FlaggedMobile))
    assert flagged.mobile == original.leader_mobile
    assert flagged.application_number == original.application_number
    assert flagged.is_blocked is False

    assert client.get("/api/officer/claims").json() == []
    queue = [item["application_number"] for item in client.get("/api/officer/queue").json()]
    assert queue == [claim.application_number]


def test_a_claim_can_be_accepted_without_flagging(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    _original, claim = claim_pair(client, db, m)
    as_dto_of(client, db, login, claim)
    client.post(f"/api/officer/claims/{claim.id}/accept", json={**OFFICER, "remarks": ""})
    assert db.scalar(select(FlaggedMobile)) is None


def test_dto_holding_a_claim_can_reject_an_application_of_another_district(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    # The same vehicle and driver were entered in an application of Cachar.
    original, claim = claim_pair(
        client, db, m, origin_district_id=m.cachar.id, origin_police_station_id=m.silchar.id
    )
    assert original.origin_district_id == m.cachar.id
    as_dto_of(client, db, login, claim)

    pair = client.get(f"/api/officer/claims/{claim.id}").json()
    assert pair["blocking"][0]["district"] == "Cachar"
    # Outside a claim, the Tinsukia DTO cannot see the Cachar application.
    assert client.get(url(original)).status_code == 404

    accepted = client.post(
        f"/api/officer/claims/{claim.id}/accept", json={**OFFICER, "remarks": ""}
    )
    assert accepted.status_code == 200, accepted.text
    db.refresh(original)
    assert original.status == Status.REJECTED
    assert "District Transport Office, Tinsukia" in last_sms(db, "APPLICATION_REJECTED").message


def test_a_claim_cannot_be_accepted_against_an_approved_permit(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    original, claim = claim_pair(client, db, m)
    original.status = Status.APPROVED  # set directly: the test is about the claim
    db.commit()
    as_dto_of(client, db, login, claim)

    refused = client.post(f"/api/officer/claims/{claim.id}/accept", json={**OFFICER, "remarks": ""})
    assert refused.status_code == 400
    assert "already approved" in refused.json()["detail"]
    db.refresh(claim)
    assert claim.status == Status.ON_HOLD_DUPLICATE_CLAIM


def test_rejecting_a_claim_closes_it_and_leaves_the_other_application_alone(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    original, claim = claim_pair(client, db, m)
    as_dto_of(client, db, login, claim)
    path = f"/api/officer/claims/{claim.id}/reject"

    assert client.post(path, json={**OFFICER, "remarks": ""}).status_code == 400

    rejected = client.post(
        path, json={**OFFICER, "remarks": "Claimant is not the owner.", "flag_mobile": True}
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "REJECTED"
    db.refresh(original)
    assert original.status == Status.PENDING_DTO
    assert db.scalar(select(FlaggedMobile)).mobile == OTHER_MOBILE
    assert "REJECTED" in last_sms(db, "APPLICATION_REJECTED").message


def test_a_claim_moves_on_when_nothing_blocks_it_any_more(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    original, claim = claim_pair(client, db, m)
    as_dto_of(client, db, login, original)
    client.post(url(original, "reject"), json={**OFFICER, "remarks": "Fake application."})

    assert client.get(f"/api/officer/claims/{claim.id}").json()["blocking"] == []
    accepted = client.post(
        f"/api/officer/claims/{claim.id}/accept", json={**OFFICER, "remarks": ""}
    )
    assert accepted.json()["status"] == "PENDING_DTO"


# ------------------------------------------------------- flagged mobiles


def test_dto_can_flag_the_mobile_when_rejecting_a_fake_application(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = fresh(client, db, m)
    as_office(client, db, login, application, Role.DTO)
    client.post(
        url(application, "reject"),
        json={**OFFICER, "remarks": "Prank application.", "flag_mobile": True},
    )
    flagged = db.scalar(select(FlaggedMobile))
    assert flagged.mobile == application.leader_mobile
    assert flagged.reason == "Prank application."
    assert OFFICER["officer_name"] in flagged.flagged_by
    assert last_audit(db, "flagged_mobile.create").entity_label == application.leader_mobile

    # A later application of that number shows a warning to officers.
    later = fresh(client, db, m, travel_date=day(20).isoformat())
    queue = client.get("/api/officer/queue").json()
    assert [item["mobile_flagged"] for item in queue] == [True]
    detail = client.get(url(later)).json()
    assert detail["mobile_flag"]["reason"] == "Prank application."
    assert detail["mobile_flag"]["application_number"] == application.application_number


def test_only_the_dto_flags_on_rejection(
    client: TestClient, db: Session, m: Masters, login: Login
) -> None:
    application = at_police(client, db, m, login)
    rejected = client.post(
        url(application, "reject"), json={**OFFICER, "remarks": "Unsafe.", "flag_mobile": True}
    )
    assert rejected.json()["status"] == "REJECTED"
    assert db.scalar(select(FlaggedMobile)) is None


def test_admin_blocks_a_flagged_number_from_applying(
    client: TestClient, db: Session, m: Masters, login: Login, admin: User
) -> None:
    application = fresh(client, db, m)
    as_office(client, db, login, application, Role.DTO)
    client.post(
        url(application, "reject"), json={**OFFICER, "remarks": "Prank.", "flag_mobile": True}
    )
    # An office user cannot manage the list.
    assert client.get("/api/admin/flagged-mobiles").status_code == 403

    client.post("/api/auth/logout")
    login(client, admin.user_id)
    rows = client.get("/api/admin/flagged-mobiles").json()
    assert [row["mobile"] for row in rows] == [application.leader_mobile]
    row_id = rows[0]["id"]

    # Flagged but not blocked: the number can still apply.
    assert submit(client, db, payload(db, m, travel_date=day(20).isoformat())).status_code == 201

    blocked = client.patch(f"/api/admin/flagged-mobiles/{row_id}", json={"is_blocked": True})
    assert blocked.json()["is_blocked"] is True
    assert last_audit(db, "flagged_mobile.update").new_value == {"is_blocked": True}

    refused = submit(client, db, payload(db, m, travel_date=day(21).isoformat()))
    assert refused.status_code == 400
    assert "cannot be used to apply" in refused.json()["detail"]
    captcha_id, answer, _ = captcha.create(db)
    db.commit()
    otp = client.post(
        "/api/public/applications/otp",
        json={
            "mobile": application.leader_mobile,
            "captcha_id": captcha_id,
            "captcha_answer": answer,
        },
    )
    assert otp.status_code == 400

    # Another number is not affected.
    other = payload(db, m, leader_mobile=THIRD_MOBILE, travel_date=day(22).isoformat())
    assert submit(client, db, other).status_code == 201

    # Lifting the block, or removing the flag, lets the number apply again.
    client.patch(f"/api/admin/flagged-mobiles/{row_id}", json={"is_blocked": False})
    assert submit(client, db, payload(db, m, travel_date=day(23).isoformat())).status_code == 201
    assert client.delete(f"/api/admin/flagged-mobiles/{row_id}").status_code == 204
    assert client.get("/api/admin/flagged-mobiles").json() == []
    assert last_audit(db, "flagged_mobile.delete").entity_label == application.leader_mobile
