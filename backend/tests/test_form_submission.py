"""Submission, the duplicate check, the OTP undertaking and uploads."""

from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.core.timeutil import now_utc, today_local
from app.models import (
    Application,
    AuditLog,
    DocType,
    InspectionStatus,
    OtpChallenge,
    SmsLog,
    Status,
    TempUpload,
    VehicleType,
)
from app.services import captcha, duplicates, otp, uploads, workflow
from app.services.validation import REQUIRED_DOCUMENTS
from tests import formkit
from tests.conftest import Masters
from tests.formkit import MOBILE, PDF, check, day, new_otp, payload, submit

# ---------------------------------------------------------------- submission


def test_submission_creates_the_application_and_routes_it_to_the_origin_dto(
    client: TestClient, db: Session, m: Masters
) -> None:
    response = submit(client, db, payload(db, m))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "PENDING_DTO"
    assert "not permission to travel" in body["message"]
    year = today_local().year % 100
    assert body["application_number"] == f"{year:02d}102200001"

    application = db.scalar(select(Application))
    assert application.status == Status.PENDING_DTO
    assert application.dto_office_id == m.dto_tinsukia.id
    assert application.origin_police_station_id == m.margherita.id
    assert application.submission_date == today_local()
    assert application.total_people == 4
    assert application.is_duplicate_claim is False
    assert application.declarations["undertaking_accepted"] is True
    assert application.declarations["kit_fire_extinguisher"] is False


def test_registration_and_licence_numbers_are_stored_without_spaces_in_capitals(
    client: TestClient, db: Session, m: Masters
) -> None:
    body = payload(db, m, vehicle_reg_number=" as 23-ab 1234 ", licence_number="as23 2019-0001234")
    assert submit(client, db, body).status_code == 201
    application = db.scalar(select(Application))
    assert application.vehicle_reg_number == "AS23-AB1234"
    assert application.vehicle_reg_key == "AS23AB1234"
    assert application.licence_number == "AS232019-0001234"
    assert application.licence_key == "AS2320190001234"


def test_group_leader_is_always_passenger_1(client: TestClient, db: Session, m: Masters) -> None:
    submit(client, db, payload(db, m))
    passengers = db.scalar(select(Application)).passengers
    assert [(p.position, p.name, p.is_group_leader) for p in passengers] == [
        (1, "Rupam Das", True),
        (2, "Mitali Das", False),
        (3, "Riya Das", False),
    ]
    assert (passengers[0].age, passengers[0].gender) == (34, "MALE")


def test_60_to_90_minutes_flags_the_application_for_the_dc(
    client: TestClient, db: Session, m: Masters
) -> None:
    submit(client, db, payload(db, m, driving_band="FROM_60_TO_90"))
    assert db.scalar(select(Application)).needs_dc_specific_approval is True


def test_application_numbers_run_per_district_and_year(
    client: TestClient, db: Session, m: Masters
) -> None:
    def number(**changes) -> str:
        response = submit(client, db, payload(db, m, **changes))
        assert response.status_code == 201, response.text
        return response.json()["application_number"]

    first = number()
    second = number(vehicle_reg_number="AS23C0002", licence_number="AS2300000000002")
    cachar = number(
        vehicle_reg_number="AS11C0003",
        licence_number="AS1100000000003",
        origin_district_id=m.cachar.id,
        origin_police_station_id=m.silchar.id,
    )
    assert (first[-5:], second[-5:], cachar[-5:]) == ("00001", "00002", "00001")
    assert (first[2:6], cachar[2:6]) == ("1022", "1004")
    assert len(first) == 11 and first.isdigit()


def test_submission_sends_an_sms_and_writes_an_audit_row(
    client: TestClient, db: Session, m: Masters
) -> None:
    number = submit(client, db, payload(db, m)).json()["application_number"]

    message = db.scalar(select(SmsLog).where(SmsLog.kind == "APPLICATION_SUBMITTED"))
    assert message.mobile == MOBILE
    assert number in message.message
    assert "NOT permission to travel" in message.message
    assert "https://picnic.example.test/status" in message.message

    row = db.scalar(select(AuditLog).where(AuditLog.action == "application.submitted"))
    assert row.actor_label == "applicant" and row.actor_user_id is None
    assert row.entity_label == number
    assert row.old_value == {"status": None}
    assert row.new_value == {"status": "PENDING_DTO"}


def test_inspection_status_depends_on_the_certificate(
    client: TestClient, db: Session, m: Masters
) -> None:
    submit(client, db, payload(db, m))
    assert db.scalar(select(Application)).inspection_status == InspectionStatus.INSPECTION_REQUIRED

    documents = {d.value: formkit.temp_upload(db, d) for d in REQUIRED_DOCUMENTS}
    documents["INSPECTION_CERTIFICATE"] = formkit.temp_upload(db, DocType.INSPECTION_CERTIFICATE)
    body = payload(
        db, m, documents=documents, vehicle_reg_number="AS23C0002", licence_number="AS2300000000002"
    )
    number = submit(client, db, body).json()["application_number"]
    second = db.scalar(select(Application).where(Application.application_number == number))
    assert second.inspection_status == InspectionStatus.CERTIFICATE_UPLOADED


def test_uploads_become_documents_of_the_application(
    client: TestClient, db: Session, m: Masters
) -> None:
    body = payload(db, m)
    token = body["documents"]["RC"]
    temp_file = uploads.temp_path(db.get(TempUpload, token))
    assert temp_file.is_file()

    submit(client, db, body)

    application = db.scalar(select(Application))
    assert {d.doc_type for d in application.documents} == set(REQUIRED_DOCUMENTS)
    assert db.scalar(select(TempUpload)) is None
    assert not temp_file.exists()
    for document in application.documents:
        assert uploads.document_path(document).read_bytes() == PDF


def test_an_invalid_form_is_not_saved_and_does_not_use_up_the_otp(
    client: TestClient, db: Session, m: Masters
) -> None:
    otp_id, code = new_otp(db)
    bad = payload(db, m, departure_time="05:00")
    request = {"application": bad, "otp_id": otp_id, "otp_code": code}
    assert client.post("/api/public/applications", json=request).status_code == 422
    assert db.scalar(select(Application)) is None

    request["application"] = payload(db, m)
    assert client.post("/api/public/applications", json=request).status_code == 201


# ----------------------------------------------------------- duplicate check


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("AS23AB1234", "AS23AB1234"),
        ("AS23AB1234", "as 23 ab 1234"),
        ("AS23AB1234", "AS-23-AB-1234"),
        ("AS 23-AB 1234", "as23ab1234"),
    ],
)
def test_numbers_are_compared_without_spaces_hyphens_or_case(first: str, second: str) -> None:
    assert duplicates.comparison_key(first) == duplicates.comparison_key(second)


def other_vehicle(db: Session, m: Masters, **changes) -> dict:
    return payload(db, m, vehicle_reg_number="AS23C0002", **changes)


def other_driver(db: Session, m: Masters, **changes) -> dict:
    return payload(db, m, licence_number="AS2300000000002", **changes)


def test_same_vehicle_on_the_same_date_is_blocked_whoever_applies(
    client: TestClient, db: Session, m: Masters
) -> None:
    assert submit(client, db, payload(db, m)).status_code == 201

    again = other_driver(db, m, leader_mobile="9876511111", vehicle_reg_number="as-23 ab-1234")
    duplicate = check(client, again).json()["duplicate"]
    assert duplicate == {
        "vehicle": True,
        "driver": False,
        "message": "An application already exists for this vehicle on that date.",
    }

    response = submit(client, db, again)
    assert response.status_code == 409
    assert response.json()["duplicate"]["vehicle"] is True
    assert db.scalar(select(Application).where(Application.leader_mobile == "9876511111")) is None


def test_same_driving_licence_on_the_same_date_is_blocked(
    client: TestClient, db: Session, m: Masters
) -> None:
    submit(client, db, payload(db, m))
    again = other_vehicle(db, m, licence_number="as23-2019 0001234")
    duplicate = check(client, again).json()["duplicate"]
    assert (duplicate["vehicle"], duplicate["driver"]) == (False, True)
    assert submit(client, db, again).status_code == 409


def test_same_vehicle_and_driver_on_another_date_is_allowed(
    client: TestClient, db: Session, m: Masters
) -> None:
    submit(client, db, payload(db, m))
    later = payload(db, m, travel_date=day(11).isoformat())
    assert check(client, later).json()["duplicate"] is None
    assert submit(client, db, later).status_code == 201


def test_same_group_leader_with_a_different_vehicle_and_driver_is_allowed(
    client: TestClient, db: Session, m: Masters
) -> None:
    submit(client, db, payload(db, m))
    second_vehicle = payload(
        db, m, vehicle_reg_number="AS23C0002", licence_number="AS2300000000002"
    )
    assert submit(client, db, second_vehicle).status_code == 201


def test_active_means_every_status_except_rejected_cancelled_and_expired() -> None:
    assert {Status.REJECTED, Status.CANCELLED, Status.EXPIRED} == duplicates.INACTIVE_STATUSES
    assert {
        Status.PENDING_DTO,
        Status.ON_HOLD_DUPLICATE_CLAIM,
        Status.PENDING_POLICE,
        Status.PENDING_DC,
        Status.RETURNED_TO_APPLICANT,
        Status.APPROVED,
    } == duplicates.ACTIVE_STATUSES


@pytest.mark.parametrize("status", sorted(Status))
def test_only_active_applications_hold_the_vehicle_and_driver(
    client: TestClient, db: Session, m: Masters, status: Status
) -> None:
    submit(client, db, payload(db, m))
    # Set directly: the officer actions that lead to these statuses come in later phases.
    db.scalar(select(Application)).status = status
    db.commit()

    duplicate = check(client, payload(db, m, leader_mobile="9876511111")).json()["duplicate"]
    if status in duplicates.INACTIVE_STATUSES:
        assert duplicate is None
    else:
        assert duplicate is not None


def test_blocked_applicant_can_raise_a_claim_and_is_put_on_hold(
    client: TestClient, db: Session, m: Masters
) -> None:
    submit(client, db, payload(db, m))

    claim = payload(db, m, leader_mobile="9876511111", leader_name="Genuine Owner")
    response = submit(client, db, claim, raise_claim=True)

    assert response.status_code == 201
    assert response.json()["status"] == "ON_HOLD_DUPLICATE_CLAIM"
    assert "on hold" in response.json()["message"]

    held = db.scalar(select(Application).where(Application.leader_mobile == "9876511111"))
    assert held.status == Status.ON_HOLD_DUPLICATE_CLAIM
    assert held.is_duplicate_claim is True
    # It keeps its own submission date for the 7-day rule.
    assert held.submission_date == today_local()

    sms_row = db.scalar(select(SmsLog).where(SmsLog.kind == "APPLICATION_ON_HOLD"))
    assert sms_row.mobile == "9876511111" and "on hold" in sms_row.message
    audit_row = db.scalar(
        select(AuditLog).where(AuditLog.action == "application.submitted_as_claim")
    )
    assert audit_row.new_value == {"status": "ON_HOLD_DUPLICATE_CLAIM"}


def test_claim_flag_has_no_effect_when_there_is_no_duplicate(
    client: TestClient, db: Session, m: Masters
) -> None:
    response = submit(client, db, payload(db, m), raise_claim=True)
    assert response.json()["status"] == "PENDING_DTO"
    assert db.scalar(select(Application)).is_duplicate_claim is False


# --------------------------------------------------------------------- OTP


def captcha_fields(db: Session) -> dict[str, str]:
    captcha_id, answer, _ = captcha.create(db)
    db.commit()
    return {"captcha_id": captcha_id, "captcha_answer": answer}


def test_otp_is_sent_after_a_captcha_and_never_stored_in_plain_text(
    client: TestClient, db: Session
) -> None:
    response = client.post(
        "/api/public/applications/otp", json={"mobile": MOBILE, **captcha_fields(db)}
    )
    assert response.status_code == 200
    assert response.json()["valid_minutes"] == 5
    assert response.json()["resend_after_seconds"] == 60

    challenge = db.get(OtpChallenge, response.json()["otp_id"])
    assert len(challenge.code_hash) == 64
    logged = db.scalar(select(SmsLog).where(SmsLog.kind == "OTP"))
    assert "[OTP] is your OTP" in logged.message
    assert not any(ch.isdigit() for ch in logged.message.split(" is your OTP")[0])


def test_otp_needs_a_correct_captcha(client: TestClient, db: Session) -> None:
    no_captcha = client.post("/api/public/applications/otp", json={"mobile": MOBILE})
    assert no_captcha.status_code == 400
    wrong = {**captcha_fields(db), "captcha_answer": "WRONG"}
    assert (
        client.post("/api/public/applications/otp", json={"mobile": MOBILE, **wrong}).status_code
        == 400
    )
    assert db.scalar(select(OtpChallenge)) is None


def test_otp_has_6_digits_and_is_valid_for_5_minutes(db: Session) -> None:
    challenge, code = otp.request(db, mobile=MOBILE, purpose=otp.PURPOSE_SUBMIT)
    assert len(code) == 6 and code.isdigit()
    assert challenge.expires_at - challenge.created_at == timedelta(minutes=5)


def test_another_otp_cannot_be_sent_within_60_seconds(db: Session) -> None:
    otp.request(db, mobile=MOBILE, purpose=otp.PURPOSE_SUBMIT)
    with pytest.raises(DomainError, match="another in"):
        otp.request(db, mobile=MOBILE, purpose=otp.PURPOSE_SUBMIT)
    # A different mobile number is not affected.
    otp.request(db, mobile="9876511111", purpose=otp.PURPOSE_SUBMIT)


def test_no_more_than_5_otps_to_one_mobile_in_an_hour(db: Session) -> None:
    for minutes_ago in (50, 40, 30, 20, 10):
        challenge, _ = otp.request(db, mobile=MOBILE, purpose=otp.PURPOSE_SUBMIT)
        challenge.created_at = now_utc() - timedelta(minutes=minutes_ago)
        db.flush()
    with pytest.raises(DomainError, match="Too many OTPs"):
        otp.request(db, mobile=MOBILE, purpose=otp.PURPOSE_SUBMIT)


def test_wrong_otp_is_refused_and_3_wrong_attempts_end_it(
    client: TestClient, db: Session, m: Masters
) -> None:
    otp_id, code = new_otp(db)
    wrong = "000000" if code != "000000" else "111111"
    request = {"application": payload(db, m), "otp_id": otp_id, "otp_code": wrong}

    first = client.post("/api/public/applications", json=request)
    assert first.status_code == 400 and "2 attempt(s) left" in first.json()["detail"]
    client.post("/api/public/applications", json=request)
    third = client.post("/api/public/applications", json=request)
    assert "ask for a new OTP" in third.json()["detail"]

    # After three wrong attempts even the right code is refused.
    request["otp_code"] = code
    assert client.post("/api/public/applications", json=request).status_code == 400
    assert db.scalar(select(Application)) is None


def test_expired_otp_is_refused(client: TestClient, db: Session, m: Masters) -> None:
    otp_id, code = new_otp(db)
    db.get(OtpChallenge, otp_id).expires_at = now_utc() - timedelta(seconds=1)
    db.commit()
    request = {"application": payload(db, m), "otp_id": otp_id, "otp_code": code}
    response = client.post("/api/public/applications", json=request)
    assert response.status_code == 400 and "expired" in response.json()["detail"]


def test_otp_of_another_mobile_number_is_refused(
    client: TestClient, db: Session, m: Masters
) -> None:
    otp_id, code = new_otp(db, "9876511111")
    request = {"application": payload(db, m), "otp_id": otp_id, "otp_code": code}
    assert client.post("/api/public/applications", json=request).status_code == 400


def test_an_otp_works_for_one_submission_only(client: TestClient, db: Session, m: Masters) -> None:
    otp_id, code = new_otp(db)
    request = {"application": payload(db, m), "otp_id": otp_id, "otp_code": code}
    assert client.post("/api/public/applications", json=request).status_code == 201

    request["application"] = payload(
        db, m, vehicle_reg_number="AS23C0002", licence_number="AS2300000000002"
    )
    assert client.post("/api/public/applications", json=request).status_code == 400


def test_one_mobile_number_can_submit_3_applications_in_a_day(
    client: TestClient, db: Session, m: Masters
) -> None:
    for index in range(3):
        body = payload(
            db, m, vehicle_reg_number=f"AS23C000{index}", licence_number=f"AS230000000000{index}"
        )
        assert submit(client, db, body).status_code == 201

    fourth = payload(db, m, vehicle_reg_number="AS23C0009", licence_number="AS2300000000009")
    response = submit(client, db, fourth)
    assert response.status_code == 429
    assert "3 applications today" in response.json()["detail"]


# ------------------------------------------------------------------ uploads


def post_file(client: TestClient, name: str, content: bytes, doc_type: str = "RC"):
    return client.post(
        "/api/public/uploads",
        data={"doc_type": doc_type},
        files={"file": (name, content, "application/octet-stream")},
    )


@pytest.mark.parametrize(
    ("name", "content", "content_type"),
    [
        ("rc.pdf", PDF, "application/pdf"),
        ("photo.png", formkit.image_bytes("PNG"), "image/png"),
        ("photo.jpg", formkit.image_bytes("JPEG"), "image/jpeg"),
        # The type is taken from the content, whatever the file is called.
        ("scan.dat", formkit.image_bytes("JPEG"), "image/jpeg"),
    ],
)
def test_pdf_jpg_and_png_are_accepted(
    client: TestClient, db: Session, name: str, content: bytes, content_type: str
) -> None:
    response = post_file(client, name, content)
    assert response.status_code == 201, response.text
    upload = db.get(TempUpload, response.json()["token"])
    assert upload.content_type == content_type
    assert upload.size_bytes == len(content)


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("virus.exe", b"MZ\x90\x00 this is a program"),
        ("notes.txt", b"just some text"),
        ("fake.pdf", b"<html>not a pdf</html>"),
        ("fake.png", b"\x89PNG\r\n\x1a\n but not really a picture"),
        ("picture.gif", b"GIF89a\x01\x00\x01\x00"),
        ("empty.pdf", b""),
    ],
)
def test_other_files_are_refused(client: TestClient, name: str, content: bytes) -> None:
    assert post_file(client, name, content).status_code == 400


def test_files_over_5_mb_are_refused(client: TestClient, db: Session) -> None:
    just_fits = PDF + b"0" * (5 * 1024 * 1024 - len(PDF))
    assert post_file(client, "big.pdf", just_fits).status_code == 201
    too_big = post_file(client, "big.pdf", just_fits + b"0")
    assert too_big.status_code == 400 and "5 MB" in too_big.json()["detail"]


def test_file_is_stored_under_a_random_name(client: TestClient, db: Session) -> None:
    token = post_file(client, "../../etc/passwd.pdf", PDF).json()["token"]
    upload = db.get(TempUpload, token)
    assert upload.original_name == "passwd.pdf"
    assert "passwd" not in upload.stored_name and upload.stored_name.endswith(".pdf")
    assert len(Path(upload.stored_name).stem) == 48
    assert uploads.temp_path(upload).parent.name == "tmp"


def test_unknown_document_type_is_refused(client: TestClient) -> None:
    assert post_file(client, "x.pdf", PDF, doc_type="PASSPORT").status_code == 422


def test_an_uploaded_file_can_be_removed(client: TestClient, db: Session) -> None:
    token = post_file(client, "rc.pdf", PDF).json()["token"]
    path = uploads.temp_path(db.get(TempUpload, token))
    assert client.delete(f"/api/public/uploads/{token}").status_code == 204
    assert not path.exists() and db.get(TempUpload, token) is None
    assert client.delete(f"/api/public/uploads/{token}").status_code == 404


def test_unsubmitted_uploads_are_deleted_after_24_hours(
    client: TestClient, db: Session, m: Masters
) -> None:
    token = formkit.temp_upload(db, DocType.RC)
    upload = db.get(TempUpload, token)
    assert upload.expires_at - now_utc() > timedelta(hours=23, minutes=59)
    path = uploads.temp_path(upload)

    upload.expires_at = now_utc() - timedelta(seconds=1)
    db.commit()

    # An expired upload can no longer be used in a form ...
    documents = {d.value: formkit.temp_upload(db, d) for d in REQUIRED_DOCUMENTS if d != DocType.RC}
    documents["RC"] = token
    response = check(client, payload(db, m, documents=documents))
    assert "documents.RC" in response.json()["field_errors"]

    # ... and the clean-up, which runs with every new upload, removed it.
    assert not path.exists() and db.get(TempUpload, token) is None


# ----------------------------------------------------------------- workflow


def test_statuses_are_the_nine_of_the_prd() -> None:
    assert [s.value for s in Status] == [
        "PENDING_DTO",
        "ON_HOLD_DUPLICATE_CLAIM",
        "PENDING_POLICE",
        "PENDING_DC",
        "RETURNED_TO_APPLICANT",
        "REJECTED",
        "APPROVED",
        "CANCELLED",
        "EXPIRED",
    ]
    assert set(workflow.STATUS_LABELS) == set(Status)


@pytest.mark.parametrize(
    "target", [s for s in Status if s not in (Status.PENDING_DTO, Status.ON_HOLD_DUPLICATE_CLAIM)]
)
def test_a_new_application_can_only_go_to_the_dto_or_on_hold(db: Session, target: Status) -> None:
    with pytest.raises(DomainError, match="cannot move"):
        workflow._transition(db, Application(), target, action="test")


def test_a_submitted_application_cannot_be_submitted_again(
    client: TestClient, db: Session, m: Masters
) -> None:
    submit(client, db, payload(db, m))
    with pytest.raises(DomainError, match="cannot move"):
        workflow.submit(db, db.scalar(select(Application)), is_duplicate_claim=False)


# ------------------------------------------------------- form configuration


def test_form_config_gives_the_rules_to_the_form(client: TestClient, db: Session) -> None:
    config = client.get("/api/public/form-config").json()
    assert config["today"] == today_local().isoformat()
    assert config["min_travel_date"] == day(7).isoformat()
    assert config["max_travel_date"] == day(90).isoformat()
    assert config["season"] == {"start_date": None, "end_date": None}
    assert (config["earliest_departure_hour"], config["latest_return_hour"]) == (7, 18)
    assert (config["leader_min_age"], config["upload_max_mb"]) == (18, 5)
    assert [t["name"] for t in config["vehicle_types"]] == [
        "Car / SUV",
        "Maxi cab / Traveller",
        "Mini bus",
        "Bus",
    ]
    required = {d["doc_type"] for d in config["documents"] if d["required"]}
    assert required == {d.value for d in REQUIRED_DOCUMENTS}
    assert len(config["documents"]) == 8
    # Road tax payment proof is no longer asked for.
    assert "ROAD_TAX" not in {d["doc_type"] for d in config["documents"]}
    assert "ROAD_TAX" not in required


# ------------------------------------------- admin: vehicle types and season


def test_admin_can_add_edit_and_deactivate_vehicle_types(
    admin_client: TestClient, db: Session, m: Masters
) -> None:
    created = admin_client.post("/api/admin/vehicle-types", json={"name": " Tempo  Traveller "})
    assert created.status_code == 201 and created.json()["name"] == "Tempo Traveller"
    type_id = created.json()["id"]
    assert (
        admin_client.post("/api/admin/vehicle-types", json={"name": "tempo traveller"}).status_code
        == 409
    )

    renamed = admin_client.patch(f"/api/admin/vehicle-types/{type_id}", json={"name": "Tempo"})
    assert renamed.json()["name"] == "Tempo"

    names = [t["name"] for t in admin_client.get("/api/public/form-config").json()["vehicle_types"]]
    assert "Tempo" in names

    admin_client.patch(f"/api/admin/vehicle-types/{type_id}", json={"is_active": False})
    names = [t["name"] for t in admin_client.get("/api/public/form-config").json()["vehicle_types"]]
    assert "Tempo" not in names
    # An inactive type is refused by the form rules too, not just hidden.
    response = check(admin_client, payload(db, m, vehicle_type_id=type_id))
    assert "vehicle_type_id" in response.json()["field_errors"]


def test_vehicle_type_in_use_cannot_be_deleted(
    admin_client: TestClient, db: Session, m: Masters
) -> None:
    submit(admin_client, db, payload(db, m))
    used = db.scalar(select(Application)).vehicle_type_id
    unused = db.scalar(select(VehicleType.id).where(VehicleType.id != used).limit(1))

    assert admin_client.delete(f"/api/admin/vehicle-types/{used}").status_code == 409
    assert admin_client.delete(f"/api/admin/vehicle-types/{unused}").status_code == 204


def test_admin_sets_the_picnic_season(admin_client: TestClient, db: Session) -> None:
    assert admin_client.get("/api/admin/season").json() == {"start_date": None, "end_date": None}

    start, end = day(20).isoformat(), day(60).isoformat()
    saved = admin_client.put("/api/admin/season", json={"start_date": start, "end_date": end})
    assert saved.json() == {"start_date": start, "end_date": end}

    config = admin_client.get("/api/public/form-config").json()
    assert config["season"] == {"start_date": start, "end_date": end}
    assert config["min_travel_date"] == start
    assert config["max_travel_date"] == end

    row = db.scalar(select(AuditLog).where(AuditLog.action == "season.update"))
    assert row.new_value == {"start_date": start, "end_date": end}

    assert (
        admin_client.put("/api/admin/season", json={"start_date": end, "end_date": start})
    ).status_code == 400
    assert (admin_client.put("/api/admin/season", json={"start_date": start})).status_code == 400

    cleared = admin_client.put("/api/admin/season", json={"start_date": None, "end_date": None})
    assert cleared.json() == {"start_date": None, "end_date": None}


def test_road_tax_proof_is_no_longer_accepted_as_an_upload(client: TestClient) -> None:
    response = post_file(client, "tax.pdf", PDF, doc_type="ROAD_TAX")
    assert response.status_code == 400
    assert "not asked for" in response.json()["detail"]


def test_form_has_no_address_or_filled_by_fields(
    client: TestClient, db: Session, m: Masters
) -> None:
    body = payload(db, m)
    assert not {"leader_address", "filled_by", "centre_name"} & set(body)
    assert submit(client, db, body).status_code == 201
    columns = set(Application.__table__.columns.keys())
    assert not {"leader_address", "filled_by", "centre_name"} & columns


def test_otp_is_shown_to_the_form_in_development_only(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import Settings, get_settings
    from app.main import app

    sent = client.post(
        "/api/public/applications/otp", json={"mobile": MOBILE, **captcha_fields(db)}
    ).json()
    assert len(sent["dev_otp"]) == 6 and sent["dev_otp"].isdigit()

    # On the live site the code goes by SMS only and is never in the answer.
    production = Settings(environment="production", postgres_user="x", postgres_password="y")
    app.dependency_overrides[get_settings] = lambda: production
    live = client.post(
        "/api/public/applications/otp", json={"mobile": "9876511111", **captcha_fields(db)}
    ).json()
    assert live["dev_otp"] is None


def test_drinking_water_is_not_part_of_the_kit_checklist() -> None:
    from app.schemas.application import ApplicationIn
    from app.services.validation import REQUIRED_TICKS

    assert "kit_water" not in REQUIRED_TICKS
    assert "kit_water" not in ApplicationIn.model_fields
    assert {t for t in REQUIRED_TICKS if t.startswith("kit_")} == {
        "kit_first_aid",
        "kit_spare_tyre",
        "kit_jack",
        "kit_spanner",
    }
