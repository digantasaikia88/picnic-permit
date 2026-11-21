"""Status search, the applicant's OTP session, the inspection certificate and correction."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.core.timeutil import now_utc, today_local
from app.models import (
    ApplicantSession,
    Application,
    AuditLog,
    DocType,
    InspectionStatus,
    OtpChallenge,
    SmsLog,
    Status,
)
from app.services import captcha, uploads, workflow
from tests import formkit
from tests.conftest import Masters
from tests.formkit import MOBILE, PDF, day, payload, submit

OTHER_MOBILE = "9876511111"


def new_application(client: TestClient, db: Session, m: Masters, **changes) -> Application:
    response = submit(client, db, payload(db, m, **changes))
    assert response.status_code == 201, response.text
    number = response.json()["application_number"]
    return db.scalar(select(Application).where(Application.application_number == number))


def second_application(client: TestClient, db: Session, m: Masters, **changes) -> Application:
    """Another application that does not clash with the first one."""
    changes.setdefault("vehicle_reg_number", "AS23C0002")
    changes.setdefault("licence_number", "AS2300000000002")
    return new_application(client, db, m, **changes)


def sign_in(
    client: TestClient, db: Session, *, mobile: str | None = None, number: str | None = None
):
    """Go through captcha and OTP on the status page. Returns the OTP answer."""
    db.execute(update(OtpChallenge).values(created_at=OtpChallenge.created_at - timedelta(hours=2)))
    captcha_id, answer, _ = captcha.create(db)
    db.commit()
    sent = client.post(
        "/api/public/status-access/otp",
        json={
            "mobile": mobile,
            "application_number": number,
            "captcha_id": captcha_id,
            "captcha_answer": answer,
        },
    )
    assert sent.status_code == 200, sent.text
    body = sent.json()
    session = client.post(
        "/api/public/status-access/session",
        json={"otp_id": body["otp_id"], "otp_code": body["dev_otp"] or "000000"},
    )
    return body, session


def returned(db: Session, application: Application, *, at: Status = Status.PENDING_DTO) -> None:
    """Return an application as the office at `at` would.

    The status is set directly for the police and DC stages: the officer
    actions that move an application forward come in Phase 5.
    """
    application.status = at
    db.flush()
    workflow.return_to_applicant(
        db,
        application,
        acting=formkit.acting_for(db, application),
        remarks="The RC copy is not readable.",
    )
    db.commit()


def correction(db: Session, m: Masters, **changes) -> dict:
    """The form as sent back on correction: unchanged unless a field is given."""
    changes.setdefault("documents", {})
    return payload(db, m, **changes)


# ------------------------------------------------------- search by number


def test_anyone_can_search_by_application_number_and_sees_no_personal_details(
    client: TestClient, anonymous: TestClient, db: Session, m: Masters
) -> None:
    application = new_application(client, db, m)

    response = anonymous.get(f"/api/public/status/{application.application_number}")

    assert response.status_code == 200
    assert response.json() == {
        "application_number": application.application_number,
        "travel_date": day(10).isoformat(),
        "status": "PENDING_DTO",
        "status_label": "Pending with DTO",
        "current_office": "District Transport Office, Tinsukia",
        "remarks": None,
        "working_status": "Received",
    }


def test_application_number_may_be_typed_with_spaces_or_hyphens(
    client: TestClient, db: Session, m: Masters
) -> None:
    number = new_application(client, db, m).application_number
    spaced = f"{number[:2]} {number[2:6]}-{number[6:]}"
    assert client.get(f"/api/public/status/{spaced}").status_code == 200


@pytest.mark.parametrize("number", ["26102299999", "123", "abcdefghijk", "261022000010"])
def test_unknown_application_number_is_not_found(client: TestClient, number: str) -> None:
    assert client.get(f"/api/public/status/{number}").status_code == 404


def test_search_is_limited_to_60_an_hour_from_one_address(client: TestClient) -> None:
    for _ in range(60):
        assert client.get("/api/public/status/26102299999").status_code == 404
    assert client.get("/api/public/status/26102299999").status_code == 429


@pytest.mark.parametrize(
    ("status", "office"),
    [
        (Status.PENDING_DTO, "District Transport Office, Tinsukia"),
        (Status.ON_HOLD_DUPLICATE_CLAIM, "District Transport Office, Tinsukia"),
        (Status.PENDING_POLICE, "Margherita PS"),
        (Status.PENDING_DC, "DC Office, Tinsukia"),
        (Status.RETURNED_TO_APPLICANT, "With the applicant, for correction"),
        (Status.APPROVED, "Closed"),
        (Status.REJECTED, "Closed"),
    ],
)
def test_current_office_follows_the_status(
    client: TestClient, db: Session, m: Masters, status: Status, office: str
) -> None:
    application = new_application(client, db, m)
    application.status = status
    db.commit()
    body = client.get(f"/api/public/status/{application.application_number}").json()
    assert body["current_office"] == office


def test_remarks_are_shown_only_for_a_return_or_a_rejection(
    client: TestClient, db: Session, m: Masters
) -> None:
    application = new_application(client, db, m)
    url = f"/api/public/status/{application.application_number}"

    returned(db, application)
    body = client.get(url).json()
    assert body["status_label"] == "Returned to applicant"
    assert body["remarks"] == "The RC copy is not readable."

    application.status = Status.REJECTED
    application.status_remarks = "Vehicle has three unpaid challans."
    db.commit()
    assert client.get(url).json()["remarks"] == "Vehicle has three unpaid challans."

    application.status = Status.PENDING_DTO
    db.commit()
    assert client.get(url).json()["remarks"] is None


# ------------------------------------------------------- search by mobile


def test_search_by_mobile_needs_an_otp_and_lists_that_mobiles_applications(
    client: TestClient, anonymous: TestClient, db: Session, m: Masters
) -> None:
    first = new_application(client, db, m)
    second = second_application(client, db, m)
    other = second_application(
        client,
        db,
        m,
        leader_mobile=OTHER_MOBILE,
        vehicle_reg_number="AS23C0003",
        licence_number="AS2300000000003",
    )

    assert anonymous.get("/api/public/my/applications").status_code == 401

    sent, session = sign_in(anonymous, db, mobile=MOBILE)
    assert sent["sent_to"] is None
    assert session.status_code == 200
    assert session.json() == {"mobile": MOBILE, "expires_in_seconds": 1800}
    cookie = session.headers["set-cookie"].lower()
    assert "pp_applicant=" in cookie and "httponly" in cookie and "max-age=1800" in cookie

    listed = anonymous.get("/api/public/my/applications").json()
    assert [a["application_number"] for a in listed] == [
        second.application_number,
        first.application_number,
    ]
    assert other.application_number not in str(listed)


def test_mobile_with_no_applications_gets_the_same_answer_but_no_otp(
    client: TestClient, db: Session, m: Masters
) -> None:
    sent, session = sign_in(client, db, mobile="9000000000")

    assert set(sent) == {"otp_id", "valid_minutes", "resend_after_seconds", "sent_to", "dev_otp"}
    assert sent["dev_otp"] is None
    assert db.scalar(select(OtpChallenge).where(OtpChallenge.mobile == "9000000000")) is None
    assert db.scalar(select(SmsLog).where(SmsLog.mobile == "9000000000")) is None
    assert session.status_code == 400


def test_status_otp_needs_a_captcha_and_a_proper_mobile_number(
    client: TestClient, db: Session
) -> None:
    assert client.post("/api/public/status-access/otp", json={"mobile": MOBILE}).status_code == 400
    captcha_id, answer, _ = captcha.create(db)
    db.commit()
    bad = client.post(
        "/api/public/status-access/otp",
        json={"mobile": "12345", "captcha_id": captcha_id, "captcha_answer": answer},
    )
    assert bad.status_code == 422 and "mobile" in bad.json()["field_errors"]


def test_full_details_by_number_send_the_otp_to_the_group_leaders_mobile(
    client: TestClient, anonymous: TestClient, db: Session, m: Masters
) -> None:
    application = new_application(client, db, m)

    sent, session = sign_in(anonymous, db, number=application.application_number)

    # Only the last two digits of the leader's number are shown to the visitor.
    assert sent["sent_to"] == "********10"
    assert session.json()["mobile"] == MOBILE
    otp_sms = db.scalars(select(SmsLog).where(SmsLog.kind == "OTP")).all()[-1]
    assert otp_sms.mobile == MOBILE


def test_status_otp_cannot_be_used_to_submit_an_application(
    client: TestClient, db: Session, m: Masters
) -> None:
    new_application(client, db, m)
    captcha_id, answer, _ = captcha.create(db)
    db.execute(update(OtpChallenge).values(created_at=OtpChallenge.created_at - timedelta(hours=2)))
    db.commit()
    sent = client.post(
        "/api/public/status-access/otp",
        json={"mobile": MOBILE, "captcha_id": captcha_id, "captcha_answer": answer},
    ).json()
    body = payload(db, m, vehicle_reg_number="AS23C0002", licence_number="AS2300000000002")
    response = client.post(
        "/api/public/applications",
        json={"application": body, "otp_id": sent["otp_id"], "otp_code": sent["dev_otp"]},
    )
    assert response.status_code == 400


def test_session_ends_after_30_minutes_and_on_logout(
    client: TestClient, db: Session, m: Masters
) -> None:
    new_application(client, db, m)
    sign_in(client, db, mobile=MOBILE)
    assert client.get("/api/public/my/session").status_code == 200

    session = db.scalar(select(ApplicantSession))
    assert session.expires_at - session.created_at == timedelta(minutes=30)
    session.expires_at = now_utc() - timedelta(seconds=1)
    db.commit()
    assert client.get("/api/public/my/applications").status_code == 401

    sign_in(client, db, mobile=MOBILE)
    assert client.post("/api/public/status-access/logout").status_code == 204
    assert client.get("/api/public/my/applications").status_code == 401


# ------------------------------------------------------------ full details


def test_group_leader_sees_the_full_application_after_the_otp(
    client: TestClient, db: Session, m: Masters
) -> None:
    application = new_application(client, db, m)
    sign_in(client, db, mobile=MOBILE)

    response = client.get(f"/api/public/my/applications/{application.application_number}")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["origin_police_station"] == "Margherita PS"
    assert body["total_people"] == 4
    assert body["can_correct"] is False
    assert body["can_upload_inspection_certificate"] is True
    assert [p["name"] for p in body["passengers"]] == ["Rupam Das", "Mitali Das", "Riya Das"]
    assert body["form"]["leader_mobile"] == MOBILE
    assert body["form"]["vehicle_reg_number"] == "AS23AB1234"
    assert body["form"]["seating_capacity"] == "17"
    assert len(body["documents"]) == 5
    assert body["form"]["documents"]["RC"]["token"].startswith("existing:")


def test_one_mobile_number_never_sees_another_numbers_application(
    client: TestClient, anonymous: TestClient, db: Session, m: Masters
) -> None:
    mine = new_application(client, db, m)
    theirs = second_application(client, db, m, leader_mobile=OTHER_MOBILE)
    document = theirs.documents[0]
    sign_in(anonymous, db, mobile=MOBILE)

    base = f"/api/public/my/applications/{theirs.application_number}"
    assert anonymous.get(base).status_code == 404
    assert anonymous.get(f"{base}/documents/{document.id}").status_code == 404
    assert anonymous.put(base, json=correction(db, m)).status_code == 404
    upload = {"file": ("c.pdf", PDF, "application/pdf")}
    assert anonymous.post(f"{base}/inspection-certificate", files=upload).status_code == 404

    # A document of someone else's application is not reachable through one's own either.
    own = f"/api/public/my/applications/{mine.application_number}/documents/{document.id}"
    assert anonymous.get(own).status_code == 404


def test_group_leader_can_download_own_documents_only_with_a_session(
    client: TestClient, anonymous: TestClient, db: Session, m: Masters
) -> None:
    application = new_application(client, db, m)
    document = application.documents[0]
    url = f"/api/public/my/applications/{application.application_number}/documents/{document.id}"

    assert anonymous.get(url).status_code == 401

    sign_in(anonymous, db, mobile=MOBILE)
    response = anonymous.get(url)
    assert response.status_code == 200
    assert response.content == PDF
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "no-store"
    assert application.application_number in response.headers["content-disposition"]


# -------------------------------------------------- inspection certificate


def test_inspection_certificate_can_be_uploaded_while_with_the_dto(
    client: TestClient, db: Session, m: Masters
) -> None:
    application = new_application(client, db, m)
    assert application.inspection_status == InspectionStatus.INSPECTION_REQUIRED
    sign_in(client, db, mobile=MOBILE)
    url = f"/api/public/my/applications/{application.application_number}/inspection-certificate"

    first = client.post(url, files={"file": ("cert.pdf", PDF, "application/pdf")})

    assert first.status_code == 200, first.text
    assert first.json()["inspection_status"] == "CERTIFICATE_UPLOADED"
    db.refresh(application)
    certificates = [
        d for d in application.documents if d.doc_type == DocType.INSPECTION_CERTIFICATE
    ]
    assert len(certificates) == 1 and uploads.document_path(certificates[0]).is_file()

    row = db.scalar(
        select(AuditLog).where(AuditLog.action == "application.inspection_certificate_uploaded")
    )
    assert row.actor_label == "applicant"
    assert row.old_value == {"inspection_status": "INSPECTION_REQUIRED", "file": None}
    assert row.new_value == {"inspection_status": "CERTIFICATE_UPLOADED", "file": "cert.pdf"}

    # A second upload replaces the first: there is still one certificate.
    old_path = uploads.document_path(certificates[0])
    client.post(url, files={"file": ("better.png", formkit.image_bytes(), "image/png")})
    db.refresh(application)
    certificates = [
        d for d in application.documents if d.doc_type == DocType.INSPECTION_CERTIFICATE
    ]
    assert [c.original_name for c in certificates] == ["better.png"]
    assert not old_path.exists()


@pytest.mark.parametrize(
    "status",
    [s for s in Status if s != Status.PENDING_DTO],
)
def test_inspection_certificate_is_refused_once_the_application_has_left_the_dto(
    client: TestClient, db: Session, m: Masters, status: Status
) -> None:
    application = new_application(client, db, m)
    application.status = status
    db.commit()
    sign_in(client, db, mobile=MOBILE)

    response = client.post(
        f"/api/public/my/applications/{application.application_number}/inspection-certificate",
        files={"file": ("cert.pdf", PDF, "application/pdf")},
    )
    assert response.status_code == 400
    assert "only while the application is with the DTO" in response.json()["detail"]


def test_inspection_certificate_must_be_a_pdf_or_picture(
    client: TestClient, db: Session, m: Masters
) -> None:
    application = new_application(client, db, m)
    sign_in(client, db, mobile=MOBILE)
    response = client.post(
        f"/api/public/my/applications/{application.application_number}/inspection-certificate",
        files={"file": ("cert.docx", b"PK\x03\x04 a word file", "application/octet-stream")},
    )
    assert response.status_code == 400


# ------------------------------------------------------------------ return


def test_return_needs_remarks_and_a_pending_application(
    client: TestClient, db: Session, m: Masters
) -> None:
    application = new_application(client, db, m)
    with pytest.raises(DomainError, match="remarks"):
        workflow.return_to_applicant(
            db, application, acting=formkit.acting_for(db, application), remarks="   "
        )

    returned(db, application)
    with pytest.raises(DomainError, match="not pending with your office"):
        workflow.return_to_applicant(
            db, application, acting=formkit.acting_for(db, application), remarks="Again"
        )


@pytest.mark.parametrize("status", [s for s in Status if s not in workflow.PENDING_STATUSES])
def test_only_a_pending_application_can_be_returned(
    client: TestClient, db: Session, m: Masters, status: Status
) -> None:
    application = new_application(client, db, m)
    application.status = status
    db.flush()
    with pytest.raises(DomainError):
        workflow.return_to_applicant(
            db, application, acting=formkit.acting_for(db, application), remarks="Please correct"
        )


def test_return_remembers_the_office_sends_an_sms_and_is_audited(
    client: TestClient, db: Session, m: Masters
) -> None:
    application = new_application(client, db, m)
    returned(db, application, at=Status.PENDING_POLICE)

    assert application.status == Status.RETURNED_TO_APPLICANT
    assert application.returned_from_status == Status.PENDING_POLICE
    assert application.status_remarks == "The RC copy is not readable."

    message = db.scalar(select(SmsLog).where(SmsLog.kind == "APPLICATION_RETURNED"))
    assert "returned by Margherita PS for correction" in message.message
    assert "https://picnic.example.test/status" in message.message

    row = db.scalar(select(AuditLog).where(AuditLog.action == "application.returned"))
    assert row.old_value == {"status": "PENDING_POLICE"}
    assert row.new_value == {
        "status": "RETURNED_TO_APPLICANT",
        "remarks": "The RC copy is not readable.",
    }


# -------------------------------------------------------------- correction


def put(client: TestClient, application: Application, body: dict):
    return client.put(f"/api/public/my/applications/{application.application_number}", json=body)


def test_only_a_returned_application_can_be_corrected(
    client: TestClient, db: Session, m: Masters
) -> None:
    application = new_application(client, db, m)
    sign_in(client, db, mobile=MOBILE)
    response = put(client, application, correction(db, m))
    assert response.status_code == 400
    assert "returned for correction" in response.json()["detail"]


def test_correction_needs_the_otp_session(
    client: TestClient, anonymous: TestClient, db: Session, m: Masters
) -> None:
    application = new_application(client, db, m)
    returned(db, application)
    assert put(anonymous, application, correction(db, m)).status_code == 401


@pytest.mark.parametrize("office", workflow.PENDING_STATUSES)
def test_corrected_application_goes_back_to_the_office_that_returned_it(
    client: TestClient, db: Session, m: Masters, office: Status
) -> None:
    application = new_application(client, db, m)
    returned(db, application, at=office)
    sign_in(client, db, mobile=MOBILE)

    response = put(client, application, correction(db, m, owner_name="Bipul Chandra Gogoi"))

    assert response.status_code == 200, response.text
    assert response.json()["status"] == office.value
    db.refresh(application)
    assert application.status == office
    assert application.owner_name == "Bipul Chandra Gogoi"
    # The return is over: its remarks no longer show.
    assert application.returned_from_status is None
    assert response.json()["remarks"] is None


@pytest.mark.parametrize(
    "change",
    [{"vehicle_reg_number": "AS23Z9999"}, {"licence_number": "AS2399999999999"}],
)
@pytest.mark.parametrize("office", [Status.PENDING_POLICE, Status.PENDING_DC])
def test_changing_the_vehicle_or_driver_after_the_dto_stage_sends_it_back_to_the_dto(
    client: TestClient, db: Session, m: Masters, office: Status, change: dict
) -> None:
    application = new_application(client, db, m)
    returned(db, application, at=office)
    sign_in(client, db, mobile=MOBILE)

    response = put(client, application, correction(db, m, **change))

    assert response.json()["status"] == "PENDING_DTO"
    message = db.scalar(select(SmsLog).where(SmsLog.kind == "APPLICATION_RESUBMITTED"))
    assert "with the DTO because the vehicle or driver was changed" in message.message


def test_same_vehicle_typed_differently_is_not_a_change(
    client: TestClient, db: Session, m: Masters
) -> None:
    application = new_application(client, db, m)
    returned(db, application, at=Status.PENDING_DC)
    sign_in(client, db, mobile=MOBILE)
    response = put(client, application, correction(db, m, vehicle_reg_number="as-23 ab-1234"))
    assert response.json()["status"] == "PENDING_DC"


def test_correction_logs_every_changed_field_with_old_and_new_value(
    client: TestClient, db: Session, m: Masters
) -> None:
    application = new_application(client, db, m)
    returned(db, application)
    sign_in(client, db, mobile=MOBILE)

    body = correction(
        db,
        m,
        seating_capacity=20,
        departure_time="08:30",
        members=[{"name": "Mitali Das", "age": 31, "gender": "FEMALE"}],
    )
    assert put(client, application, body).status_code == 200

    row = db.scalar(select(AuditLog).where(AuditLog.action == "application.corrected_by_applicant"))
    assert row.actor_label == "applicant"
    assert row.old_value["seating_capacity"] == 17 and row.new_value["seating_capacity"] == 20
    assert row.old_value["departure_time"] == "07:00:00"
    assert row.new_value["departure_time"] == "08:30:00"
    assert len(row.old_value["passengers"]) == 2 and len(row.new_value["passengers"]) == 1
    # Fields that did not change are not listed.
    assert "owner_name" not in row.new_value

    resubmitted = db.scalar(select(AuditLog).where(AuditLog.action == "application.resubmitted"))
    assert resubmitted.new_value == {"status": "PENDING_DTO"}


def test_group_leader_stays_passenger_1_after_correction(
    client: TestClient, db: Session, m: Masters
) -> None:
    application = new_application(client, db, m)
    returned(db, application)
    sign_in(client, db, mobile=MOBILE)
    body = correction(
        db, m, leader_name="Rupam Kumar Das", members=[{"name": "New", "age": 40, "gender": "MALE"}]
    )
    put(client, application, body)
    db.refresh(application)
    assert [(p.position, p.name, p.is_group_leader) for p in application.passengers] == [
        (1, "Rupam Kumar Das", True),
        (2, "New", False),
    ]
    assert application.total_people == 3


def test_mobile_number_and_starting_district_cannot_be_changed(
    client: TestClient, db: Session, m: Masters
) -> None:
    application = new_application(client, db, m)
    returned(db, application)
    sign_in(client, db, mobile=MOBILE)

    body = correction(
        db,
        m,
        leader_mobile=OTHER_MOBILE,
        origin_district_id=m.cachar.id,
        origin_police_station_id=m.silchar.id,
    )
    response = put(client, application, body)

    assert response.status_code == 422
    assert set(response.json()["field_errors"]) == {"leader_mobile", "origin_district_id"}
    db.refresh(application)
    assert application.status == Status.RETURNED_TO_APPLICANT


def test_form_rules_hold_for_corrected_data(client: TestClient, db: Session, m: Masters) -> None:
    application = new_application(client, db, m)
    returned(db, application)
    sign_in(client, db, mobile=MOBILE)

    response = put(
        client, application, correction(db, m, departure_time="05:00", seating_capacity=2)
    )
    assert response.status_code == 422
    assert {"departure_time", "members"} <= set(response.json()["field_errors"])
    db.refresh(application)
    assert application.status == Status.RETURNED_TO_APPLICANT


def test_the_7_and_90_days_count_from_the_original_submission_date(
    client: TestClient, db: Session, m: Masters
) -> None:
    application = new_application(client, db, m)
    # Submitted 20 days ago, returned today.
    application.submission_date = today_local() - timedelta(days=20)
    returned(db, application)
    sign_in(client, db, mobile=MOBILE)

    # Two days from today is 22 days after submission: allowed.
    soon = correction(db, m, travel_date=day(2).isoformat())
    assert put(client, application, soon).status_code == 200

    returned(db, application)
    # 80 days from today is 100 days after submission: over the 90-day limit.
    late = put(client, application, correction(db, m, travel_date=day(80).isoformat()))
    assert late.status_code == 422 and "travel_date" in late.json()["field_errors"]


def test_duplicate_check_ignores_the_application_itself_but_not_others(
    client: TestClient, db: Session, m: Masters
) -> None:
    application = new_application(client, db, m)
    second_application(client, db, m, leader_mobile=OTHER_MOBILE)
    returned(db, application)
    sign_in(client, db, mobile=MOBILE)

    # Unchanged vehicle and driver: its own row is not a duplicate.
    assert put(client, application, correction(db, m)).status_code == 200

    returned(db, application)
    # Changing to the vehicle of the other application on that date is blocked.
    clash = put(client, application, correction(db, m, vehicle_reg_number="AS23C0002"))
    assert clash.status_code == 409
    assert clash.json()["duplicate"]["vehicle"] is True


def test_documents_stay_unless_replaced(client: TestClient, db: Session, m: Masters) -> None:
    application = new_application(client, db, m)
    returned(db, application)
    sign_in(client, db, mobile=MOBILE)
    before = {d.doc_type: d.stored_name for d in application.documents}
    old_rc = uploads.document_path(
        next(d for d in application.documents if d.doc_type == DocType.RC)
    )

    detail = client.get(f"/api/public/my/applications/{application.application_number}").json()
    documents = {doc: item["token"] for doc, item in detail["form"]["documents"].items()}
    documents["RC"] = formkit.temp_upload(db, DocType.RC, formkit.image_bytes())
    documents["INSPECTION_CERTIFICATE"] = formkit.temp_upload(db, DocType.INSPECTION_CERTIFICATE)

    response = put(client, application, correction(db, m, documents=documents))

    assert response.status_code == 200, response.text
    db.refresh(application)
    after = {d.doc_type: d.stored_name for d in application.documents}
    assert after[DocType.RC] != before[DocType.RC] and not old_rc.exists()
    assert after[DocType.INSURANCE] == before[DocType.INSURANCE]
    assert DocType.INSPECTION_CERTIFICATE in after
    assert application.inspection_status == InspectionStatus.CERTIFICATE_UPLOADED

    row = db.scalar(select(AuditLog).where(AuditLog.action == "application.corrected_by_applicant"))
    assert row.new_value["documents_replaced"] == ["INSPECTION_CERTIFICATE", "RC"]


# ------------------------------------------------------ emergency contacts


def test_admin_maintains_emergency_contacts_and_the_public_sees_active_ones(
    admin_client: TestClient, anonymous: TestClient, db: Session, m: Masters
) -> None:
    created = admin_client.post(
        "/api/admin/emergency-contacts",
        json={
            "district_id": m.tinsukia.id,
            "name": " District Police  Control Room ",
            "phone": "0374 2331200",
        },
    )
    assert created.status_code == 201
    contact = created.json()
    assert contact["name"] == "District Police Control Room"
    admin_client.post(
        "/api/admin/emergency-contacts",
        json={"district_id": m.cachar.id, "name": "Civil Hospital", "phone": "03842 245000"},
    )

    public = anonymous.get("/api/public/emergency-contacts", params={"district_id": m.tinsukia.id})
    assert [(c["name"], c["phone"]) for c in public.json()] == [
        ("District Police Control Room", "0374 2331200")
    ]

    admin_client.patch(f"/api/admin/emergency-contacts/{contact['id']}", json={"is_active": False})
    public = anonymous.get("/api/public/emergency-contacts", params={"district_id": m.tinsukia.id})
    assert public.json() == []

    assert admin_client.delete(f"/api/admin/emergency-contacts/{contact['id']}").status_code == 204
    actions = set(
        db.scalars(select(AuditLog.action).where(AuditLog.entity_type == "emergency_contact"))
    )
    assert actions == {
        "emergency_contact.create",
        "emergency_contact.update",
        "emergency_contact.delete",
    }


def test_a_duplicate_claim_against_an_application_does_not_block_its_correction(
    client: TestClient, db: Session, m: Masters
) -> None:
    application = new_application(client, db, m)
    # Someone raises a claim on the same vehicle and driver: it is on hold, and active.
    claim = submit(client, db, payload(db, m, leader_mobile=OTHER_MOBILE), raise_claim=True)
    assert claim.json()["status"] == "ON_HOLD_DUPLICATE_CLAIM"
    returned(db, application)
    sign_in(client, db, mobile=MOBILE)

    # Correcting other details, with the same vehicle, driver and date, is allowed.
    same = put(client, application, correction(db, m, owner_name="Bipul Chandra Gogoi"))
    assert same.status_code == 200, same.text

    # Moving the date onto another application's vehicle is still a clash.
    other = second_application(
        client,
        db,
        m,
        leader_mobile="9876522222",
        travel_date=day(12).isoformat(),
        vehicle_reg_number="AS23AB1234",
        licence_number="AS2300000000005",
    )
    assert other.status == Status.PENDING_DTO
    returned(db, application)
    moved = put(client, application, correction(db, m, travel_date=day(12).isoformat()))
    assert moved.status_code == 409 and moved.json()["duplicate"]["vehicle"] is True
