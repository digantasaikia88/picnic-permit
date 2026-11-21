"""Every hard rule of the application form (PRD Sections 4 and 6)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import AppSetting, DocType, PicnicSeason
from app.services.validation import REQUIRED_DOCUMENTS, REQUIRED_TICKS
from tests import formkit
from tests.conftest import Masters
from tests.formkit import check, day, payload


def errors_of(response) -> dict[str, str]:
    assert response.status_code == 422, response.text
    return response.json()["field_errors"]


def assert_ok(response) -> None:
    assert response.status_code == 200, response.text


def set_setting(db: Session, key: str, value: int) -> None:
    db.get(AppSetting, key).value = value
    db.commit()


def test_a_complete_form_passes(client: TestClient, db: Session, m: Masters) -> None:
    response = check(client, payload(db, m))
    assert_ok(response)
    # Leader, 2 members and the driver.
    assert response.json() == {"total_people": 4, "duplicate": None}


# ------------------------------------------------------------- travel date


@pytest.mark.parametrize(
    ("offset", "ok"), [(6, False), (7, True), (8, True), (90, True), (91, False), (-1, False)]
)
def test_travel_date_is_7_to_90_days_after_submission(
    client: TestClient, db: Session, m: Masters, offset: int, ok: bool
) -> None:
    response = check(client, payload(db, m, travel_date=day(offset).isoformat()))
    if ok:
        assert_ok(response)
    else:
        assert "travel_date" in errors_of(response)


def test_travel_date_messages_name_the_rule(client: TestClient, db: Session, m: Masters) -> None:
    early = errors_of(check(client, payload(db, m, travel_date=day(3).isoformat())))
    assert "at least 7 days" in early["travel_date"]
    late = errors_of(check(client, payload(db, m, travel_date=day(120).isoformat())))
    assert "more than 90 days" in late["travel_date"]


def test_minimum_and_maximum_days_are_settings(client: TestClient, db: Session, m: Masters) -> None:
    set_setting(db, "min_days_before_travel", 10)
    set_setting(db, "max_days_before_travel", 30)
    assert "travel_date" in errors_of(check(client, payload(db, m, travel_date=day(9).isoformat())))
    assert_ok(check(client, payload(db, m, travel_date=day(10).isoformat())))
    assert_ok(check(client, payload(db, m, travel_date=day(30).isoformat())))
    assert "travel_date" in errors_of(
        check(client, payload(db, m, travel_date=day(31).isoformat()))
    )


def test_travel_date_must_fall_in_the_picnic_season_when_one_is_set(
    client: TestClient, db: Session, m: Masters
) -> None:
    season = db.get(PicnicSeason, 1)
    season.start_date, season.end_date = day(20), day(40)
    db.commit()

    before = errors_of(check(client, payload(db, m, travel_date=day(19).isoformat())))
    assert "picnic season" in before["travel_date"]
    assert_ok(check(client, payload(db, m, travel_date=day(20).isoformat())))
    assert_ok(check(client, payload(db, m, travel_date=day(40).isoformat())))
    assert "travel_date" in errors_of(
        check(client, payload(db, m, travel_date=day(41).isoformat()))
    )


def test_no_season_limit_until_the_admin_sets_the_dates(
    client: TestClient, db: Session, m: Masters
) -> None:
    assert db.get(PicnicSeason, 1).start_date is None
    assert_ok(check(client, payload(db, m, travel_date=day(60).isoformat())))


# ------------------------------------------------------------------- hours


@pytest.mark.parametrize(
    ("departure", "returning", "bad_field"),
    [
        ("07:00", "18:00", None),
        ("06:59", "18:00", "departure_time"),
        ("00:00", "18:00", "departure_time"),
        ("07:00", "18:01", "return_time"),
        ("07:00", "23:00", "return_time"),
        ("10:00", "10:00", "return_time"),
        ("12:00", "09:00", "return_time"),
        ("09:30", "16:45", None),
    ],
)
def test_departure_not_before_7_and_return_by_6_and_after_departure(
    client: TestClient,
    db: Session,
    m: Masters,
    departure: str,
    returning: str,
    bad_field: str | None,
) -> None:
    response = check(client, payload(db, m, departure_time=departure, return_time=returning))
    if bad_field is None:
        assert_ok(response)
    else:
        assert bad_field in errors_of(response)


def test_permitted_hours_are_settings(client: TestClient, db: Session, m: Masters) -> None:
    set_setting(db, "earliest_departure_hour", 8)
    set_setting(db, "latest_return_hour", 17)
    errors = errors_of(check(client, payload(db, m, departure_time="07:30", return_time="17:30")))
    assert "8:00 AM" in errors["departure_time"]
    assert "5:00 PM" in errors["return_time"]


# -------------------------------------------------------------- the leader


@pytest.mark.parametrize(("age", "ok"), [(17, False), (18, True), (120, True), (121, False)])
def test_group_leader_must_be_18_or_over(
    client: TestClient, db: Session, m: Masters, age: int, ok: bool
) -> None:
    response = check(client, payload(db, m, leader_age=age))
    if ok:
        assert_ok(response)
    else:
        assert "leader_age" in errors_of(response)


@pytest.mark.parametrize("mobile", ["", "12345", "5876543210", "98765432101", "98765abcde"])
@pytest.mark.parametrize("field", ["leader_mobile", "owner_mobile", "driver_mobile"])
def test_mobile_numbers_are_10_digits_starting_6_to_9(
    client: TestClient, db: Session, m: Masters, field: str, mobile: str
) -> None:
    assert field in errors_of(check(client, payload(db, m, **{field: mobile})))


@pytest.mark.parametrize(
    "field",
    [
        "leader_name",
        "origin_address",
        "destination_address",
        "owner_name",
        "driver_name",
        "licence_class",
    ],
)
def test_mandatory_text_fields(client: TestClient, db: Session, m: Masters, field: str) -> None:
    assert field in errors_of(check(client, payload(db, m, **{field: "   "})))


# ------------------------------------------------- districts and stations


def test_origin_police_station_must_belong_to_the_origin_district(
    client: TestClient, db: Session, m: Masters
) -> None:
    errors = errors_of(check(client, payload(db, m, origin_police_station_id=m.silchar.id)))
    assert "origin_police_station_id" in errors


def test_inactive_district_or_station_cannot_be_chosen(
    client: TestClient, db: Session, m: Masters
) -> None:
    m.margherita.is_active = False
    db.commit()
    assert "origin_police_station_id" in errors_of(check(client, payload(db, m)))

    m.tinsukia.is_active = False
    db.commit()
    errors = errors_of(check(client, payload(db, m)))
    assert "origin_district_id" in errors and "destination_district_id" in errors


def test_district_without_a_dto_office_cannot_accept_applications(
    client: TestClient, db: Session, m: Masters
) -> None:
    body = payload(db, m, origin_district_id=m.goalpara.id, origin_police_station_id=m.lakhipur.id)
    assert "No DTO office" in errors_of(check(client, body))["origin_district_id"]


def test_destination_police_station_is_optional_but_must_match_the_district(
    client: TestClient, db: Session, m: Masters
) -> None:
    assert_ok(check(client, payload(db, m, destination_police_station_id=None)))
    assert_ok(check(client, payload(db, m, destination_police_station_id=m.digboi.id)))
    wrong = check(client, payload(db, m, destination_police_station_id=m.silchar.id))
    assert "destination_police_station_id" in errors_of(wrong)
    # The destination may be in another district.
    other = payload(
        db, m, destination_district_id=m.cachar.id, destination_police_station_id=m.silchar.id
    )
    assert_ok(check(client, other))


def test_driving_time_offers_two_bands_only(client: TestClient, db: Session, m: Masters) -> None:
    assert_ok(check(client, payload(db, m, driving_band="UP_TO_60")))
    assert_ok(check(client, payload(db, m, driving_band="FROM_60_TO_90")))
    over = check(client, payload(db, m, driving_band="OVER_90"))
    assert over.status_code == 422


# ----------------------------------------------------------------- vehicle


@pytest.mark.parametrize("number", ["", "AS1", "AS01 AB 1234 5678 99", "AS01/AB/1234", "!!!!!!"])
def test_registration_number_must_look_like_one(
    client: TestClient, db: Session, m: Masters, number: str
) -> None:
    assert "vehicle_reg_number" in errors_of(
        check(client, payload(db, m, vehicle_reg_number=number))
    )


@pytest.mark.parametrize("number", ["AS01AB1234", "as 01 ab 1234", "AS-01-AB-1234", "22BH1234AA"])
def test_registration_number_accepts_spaces_hyphens_and_any_case(
    client: TestClient, db: Session, m: Masters, number: str
) -> None:
    assert_ok(check(client, payload(db, m, vehicle_reg_number=number)))


def test_vehicle_type_must_be_an_active_type_from_the_master(
    client: TestClient, db: Session, m: Masters
) -> None:
    assert "vehicle_type_id" in errors_of(check(client, payload(db, m, vehicle_type_id=999999)))


@pytest.mark.parametrize("capacity", [0, -3, 101])
def test_seating_capacity_range(client: TestClient, db: Session, m: Masters, capacity: int) -> None:
    assert "seating_capacity" in errors_of(check(client, payload(db, m, seating_capacity=capacity)))


# ------------------------------------------------------------------ driver


def test_licence_must_be_valid_on_the_travel_date(
    client: TestClient, db: Session, m: Masters
) -> None:
    travel = day(10)
    same_day = payload(
        db, m, travel_date=travel.isoformat(), licence_valid_until=travel.isoformat()
    )
    assert_ok(check(client, same_day))
    day_before = payload(
        db, m, travel_date=travel.isoformat(), licence_valid_until=day(9).isoformat()
    )
    assert "licence_valid_until" in errors_of(check(client, day_before))


def test_handyman_details_are_mandatory_only_when_a_handyman_travels(
    client: TestClient, db: Session, m: Masters
) -> None:
    errors = errors_of(check(client, payload(db, m, has_handyman=True)))
    assert {"handyman_name", "handyman_mobile"} <= set(errors)
    with_handyman = payload(
        db, m, has_handyman=True, handyman_name="Ratul Deka", handyman_mobile="9876500003"
    )
    assert_ok(check(client, with_handyman))


# -------------------------------------------------------------- passengers


def members(count: int, age: int = 30) -> list[dict[str, Any]]:
    return [{"name": f"Member {i}", "age": age, "gender": "FEMALE"} for i in range(count)]


def test_people_must_not_exceed_the_seating_capacity(
    client: TestClient, db: Session, m: Masters
) -> None:
    # Capacity 7: leader + 5 members + driver = 7 is allowed.
    full = check(client, payload(db, m, seating_capacity=7, members=members(5)))
    assert_ok(full)
    assert full.json()["total_people"] == 7

    # One more member does not fit.
    over = errors_of(check(client, payload(db, m, seating_capacity=7, members=members(6))))
    assert "8 people are travelling" in over["members"]
    assert "7 seats" in over["members"]


def test_driver_and_handyman_count_towards_the_seats(
    client: TestClient, db: Session, m: Masters
) -> None:
    # Leader + 5 members + driver + handyman = 8, one more than the 7 seats.
    body = payload(
        db,
        m,
        seating_capacity=7,
        members=members(5),
        has_handyman=True,
        handyman_name="Ratul Deka",
        handyman_mobile="9876500003",
    )
    assert "members" in errors_of(check(client, body))


def test_a_group_leader_alone_with_a_driver_is_allowed(
    client: TestClient, db: Session, m: Masters
) -> None:
    response = check(client, payload(db, m, seating_capacity=2, members=[]))
    assert_ok(response)
    assert response.json()["total_people"] == 2


def test_child_counting_rule_is_a_setting(client: TestClient, db: Session, m: Masters) -> None:
    group = [*members(5), {"name": "Baby", "age": 2, "gender": "MALE"}]
    # Starting rule: every person counts, so 8 people do not fit 7 seats.
    assert "members" in errors_of(check(client, payload(db, m, seating_capacity=7, members=group)))

    # If the department decides children under 5 need no seat, the same group fits.
    set_setting(db, "child_free_below_age", 5)
    response = check(client, payload(db, m, seating_capacity=7, members=group))
    assert_ok(response)
    assert response.json()["total_people"] == 7


def test_each_passenger_needs_a_name_and_a_sensible_age(
    client: TestClient, db: Session, m: Masters
) -> None:
    group = [
        {"name": "", "age": 30, "gender": "MALE"},
        {"name": "Old", "age": 130, "gender": "MALE"},
    ]
    errors = errors_of(check(client, payload(db, m, members=group)))
    assert "members.0.name" in errors and "members.1.age" in errors


# ------------------------------------------------------ ticks and documents


@pytest.mark.parametrize("tick", sorted(REQUIRED_TICKS))
def test_every_declaration_and_kit_tick_is_mandatory(
    client: TestClient, db: Session, m: Masters, tick: str
) -> None:
    assert tick in errors_of(check(client, payload(db, m, **{tick: False})))


def test_fire_extinguisher_is_optional(client: TestClient, db: Session, m: Masters) -> None:
    assert_ok(check(client, payload(db, m, kit_fire_extinguisher=False)))


@pytest.mark.parametrize("doc_type", sorted(REQUIRED_DOCUMENTS))
def test_required_documents(client: TestClient, db: Session, m: Masters, doc_type: DocType) -> None:
    documents = {d.value: formkit.temp_upload(db, d) for d in REQUIRED_DOCUMENTS if d != doc_type}
    errors = errors_of(check(client, payload(db, m, documents=documents)))
    assert f"documents.{doc_type.value}" in errors


def test_inspection_certificate_permit_and_sld_are_optional(
    client: TestClient, db: Session, m: Masters
) -> None:
    documents = {d.value: formkit.temp_upload(db, d) for d in DocType}
    assert_ok(check(client, payload(db, m, documents=documents)))
    assert_ok(check(client, payload(db, m)))


def test_document_token_must_be_a_live_upload_of_the_same_kind(
    client: TestClient, db: Session, m: Masters
) -> None:
    documents = {d.value: formkit.temp_upload(db, d) for d in REQUIRED_DOCUMENTS}
    documents["RC"] = documents["INSURANCE"]
    assert "documents.RC" in errors_of(check(client, payload(db, m, documents=documents)))

    documents["RC"] = "00000000-0000-0000-0000-000000000000"
    assert "documents.RC" in errors_of(check(client, payload(db, m, documents=documents)))


def test_all_problems_are_reported_together(client: TestClient, db: Session, m: Masters) -> None:
    body = payload(
        db, m, leader_age=10, departure_time="05:00", owner_mobile="1", undertaking_accepted=False
    )
    errors = errors_of(check(client, body))
    assert {"leader_age", "departure_time", "owner_mobile", "undertaking_accepted"} <= set(errors)
