"""User ID naming rules (PRD Section 3.2)."""

import csv
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import District, DtoOffice, PoliceStation, Role
from app.seeds import load_masters
from app.services import masters, users
from app.services.user_ids import is_valid_user_id, normalise_user_id, station_slug
from app.services.users import OfficeLink
from tests.conftest import Masters

MASTERS_DIR = Path(get_settings().masters_dir)


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("Margherita PS", "margherita"),
        ("Barpeta Road PS", "barpetaroad"),
        ("R.K. Nagar PS", "rknagar"),
        ("Sam elangso PS", "samelangso"),
        ("Goalpara PS", "goalpara"),
        ("All Women PS", "allwomen"),
        ("  dispur ps ", "dispur"),
    ],
)
def test_station_slug_drops_spaces_dots_and_trailing_ps(name: str, slug: str) -> None:
    assert station_slug(name) == slug


@pytest.mark.parametrize("user_id", ["dto.tinsukia", "ps.lakhipur.cachar", "admin.1", "dto.x.2"])
def test_valid_user_ids(user_id: str) -> None:
    assert is_valid_user_id(user_id)


@pytest.mark.parametrize("user_id", ["DTO.Tinsukia", "dto tinsukia", "dto..x", ".dto", "dto-x", ""])
def test_invalid_user_ids(user_id: str) -> None:
    assert not is_valid_user_id(user_id)


def test_login_user_id_is_not_case_sensitive() -> None:
    assert normalise_user_id("  DTO.Tinsukia ") == "dto.tinsukia"


def test_generator_reproduces_all_376_user_ids_of_the_master_list(db: Session) -> None:
    """The naming rules, applied to the masters, give exactly User_ID_List.csv."""
    seed = load_masters
    masters.import_districts(
        db, None, seed._read(MASTERS_DIR, "District_Master.csv", masters.DISTRICT_COLUMNS)
    )
    masters.import_police_stations(
        db,
        None,
        seed._read(MASTERS_DIR, "Police_Stations_master.csv", masters.POLICE_STATION_COLUMNS),
    )
    masters.import_dto_offices(
        db, None, seed._read(MASTERS_DIR, "DTO_Office_Master.csv", masters.DTO_OFFICE_COLUMNS)
    )

    with (MASTERS_DIR / "User_ID_List.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 376

    for row in rows:
        district = db.scalar(select(District).where(District.code == int(row["District ID"])))
        if row["Role"] == "DTO":
            role = Role.DTO
            link = OfficeLink(
                dto_office=db.scalar(select(DtoOffice).where(DtoOffice.district_id == district.id))
            )
        elif row["Role"] == "DC Office":
            role, link = Role.DC_OFFICE, OfficeLink(district=district)
        else:
            role = Role.POLICE_STATION
            station = db.scalar(
                select(PoliceStation).where(
                    PoliceStation.district_id == district.id,
                    func.lower(PoliceStation.name) == row["Office Name"].lower(),
                )
            )
            assert station is not None, row["Office Name"]
            link = OfficeLink(police_station=station)

        user, _ = users.create_user(db, None, role=role, link=link, with_password=False)
        assert user.user_id == row["User ID"], row["Office Name"]


def test_second_and_third_user_of_an_office_get_a_number(db: Session, m: Masters) -> None:
    link = OfficeLink(dto_office=m.dto_tinsukia)
    ids = [users.create_user(db, None, role=Role.DTO, link=link)[0].user_id for _ in range(3)]
    assert ids == ["dto.tinsukia", "dto.tinsukia.2", "dto.tinsukia.3"]


def test_police_station_name_clash_adds_the_district_short_name(db: Session, m: Masters) -> None:
    first, _ = users.create_user(
        db, None, role=Role.POLICE_STATION, link=OfficeLink(police_station=m.lakhipur)
    )
    assert first.user_id == "ps.lakhipur"

    other = masters.create_police_station(db, None, name="Lakhipur PS", district_id=m.cachar.id)
    link = OfficeLink(police_station=other)
    clash, _ = users.create_user(db, None, role=Role.POLICE_STATION, link=link)
    assert clash.user_id == "ps.lakhipur.cachar"

    second, _ = users.create_user(db, None, role=Role.POLICE_STATION, link=link)
    assert second.user_id == "ps.lakhipur.cachar.2"


def test_name_clash_is_detected_even_before_the_first_station_has_a_user(
    db: Session, m: Masters
) -> None:
    other = masters.create_police_station(db, None, name="Lakhipur PS", district_id=m.cachar.id)
    user, _ = users.create_user(
        db, None, role=Role.POLICE_STATION, link=OfficeLink(police_station=other)
    )
    assert user.user_id == "ps.lakhipur.cachar"


def test_dc_admin_and_viewer_user_ids(db: Session, m: Masters) -> None:
    def new(role: Role, **link: object) -> str:
        return users.create_user(db, None, role=role, link=OfficeLink(**link))[0].user_id

    assert new(Role.DC_OFFICE, district=m.tinsukia) == "dc.tinsukia"
    assert new(Role.STATE_ADMIN) == "admin.1"
    assert new(Role.STATE_ADMIN) == "admin.2"
    assert new(Role.VIEWER, district=m.tinsukia) == "sp.tinsukia"
    assert new(Role.VIEWER) == "transport.state.1"
    assert new(Role.VIEWER) == "transport.state.2"
