"""Districts, police stations and DTO offices."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import District, PoliceStation, Role
from tests.conftest import MakeUser, Masters


def test_public_lists_show_only_active_rows(
    client: TestClient, admin_client: TestClient, m: Masters
) -> None:
    names = [d["name"] for d in client.get("/api/public/districts").json()]
    assert names == ["Cachar", "Goalpara", "Tinsukia"]

    stations = client.get("/api/public/police-stations", params={"district_id": m.tinsukia.id})
    assert [s["name"] for s in stations.json()] == ["Digboi PS", "Margherita PS"]

    admin_client.patch(f"/api/admin/police-stations/{m.digboi.id}", json={"is_active": False})
    admin_client.patch(f"/api/admin/districts/{m.cachar.id}", json={"is_active": False})

    stations = client.get("/api/public/police-stations", params={"district_id": m.tinsukia.id})
    assert [s["name"] for s in stations.json()] == ["Margherita PS"]
    assert [d["name"] for d in client.get("/api/public/districts").json()] == [
        "Goalpara",
        "Tinsukia",
    ]
    # The admin still sees inactive rows.
    assert len(admin_client.get("/api/admin/districts").json()) == 3


def test_public_lists_need_no_login_and_expose_only_id_and_name(
    anonymous: TestClient, m: Masters
) -> None:
    body = anonymous.get("/api/public/districts").json()
    assert set(body[0]) == {"id", "name"}


def test_add_district_checks_id_name_and_short_name(admin_client: TestClient, m: Masters) -> None:
    ok = admin_client.post(
        "/api/admin/districts", json={"code": 1008, "name": "Dibrugarh", "short_name": "Dibrugarh"}
    )
    assert ok.status_code == 201
    assert ok.json()["short_name"] == "dibrugarh"

    def add(code: int, name: str, short_name: str) -> int:
        return admin_client.post(
            "/api/admin/districts", json={"code": code, "name": name, "short_name": short_name}
        ).status_code

    assert add(1008, "Other", "other") == 409
    assert add(2000, "dibrugarh", "other") == 409
    assert add(2000, "Other", "dibrugarh") == 409
    assert add(2000, "Other", "two words") == 400
    assert add(0, "Other", "other") == 400


def test_district_short_name_is_editable(admin_client: TestClient, m: Masters) -> None:
    response = admin_client.patch(
        f"/api/admin/districts/{m.tinsukia.id}", json={"short_name": "tsk"}
    )
    assert response.status_code == 200
    assert response.json()["short_name"] == "tsk"
    created = admin_client.post(
        "/api/admin/users", json={"role": "DC_OFFICE", "district_id": m.tinsukia.id}
    )
    assert created.json()["user"]["user_id"] == "dc.tsk"


def test_police_station_name_is_unique_within_a_district_only(
    admin_client: TestClient, m: Masters
) -> None:
    same_district = admin_client.post(
        "/api/admin/police-stations", json={"name": "margherita ps", "district_id": m.tinsukia.id}
    )
    assert same_district.status_code == 409

    other_district = admin_client.post(
        "/api/admin/police-stations", json={"name": "Margherita PS", "district_id": m.cachar.id}
    )
    assert other_district.status_code == 201


def test_police_station_can_be_renamed_and_moved(admin_client: TestClient, m: Masters) -> None:
    response = admin_client.patch(
        f"/api/admin/police-stations/{m.digboi.id}",
        json={"name": "Digboi Town PS", "district_id": m.cachar.id},
    )
    assert response.status_code == 200
    assert response.json() == {
        "id": m.digboi.id,
        "name": "Digboi Town PS",
        "district_id": m.cachar.id,
        "is_active": True,
    }


def test_master_row_in_use_cannot_be_deleted_only_deactivated(
    admin_client: TestClient, make_user: MakeUser, m: Masters, db: Session
) -> None:
    make_user(Role.POLICE_STATION, police_station=m.margherita)
    make_user(Role.DTO, dto_office=m.dto_tinsukia)

    for path in (
        f"/api/admin/police-stations/{m.margherita.id}",
        f"/api/admin/dto-offices/{m.dto_tinsukia.id}",
        f"/api/admin/districts/{m.tinsukia.id}",
    ):
        response = admin_client.delete(path)
        assert response.status_code == 409, path
        assert "inactive" in response.json()["detail"]

    assert db.get(PoliceStation, m.margherita.id) is not None
    deactivated = admin_client.patch(
        f"/api/admin/police-stations/{m.margherita.id}", json={"is_active": False}
    )
    assert deactivated.json()["is_active"] is False


def test_unused_master_row_can_be_deleted(
    admin_client: TestClient, m: Masters, db: Session
) -> None:
    assert admin_client.delete(f"/api/admin/police-stations/{m.silchar.id}").status_code == 204
    assert admin_client.delete(f"/api/admin/dto-offices/{m.dto_cachar.id}").status_code == 204
    assert admin_client.delete(f"/api/admin/districts/{m.cachar.id}").status_code == 204
    assert db.get(District, m.cachar.id) is None


def test_dto_office_add_and_modify(admin_client: TestClient, m: Masters) -> None:
    created = admin_client.post(
        "/api/admin/dto-offices",
        json={
            "code": "dto-1009",
            "name": "District Transport Office, Goalpara",
            "district_id": m.goalpara.id,
        },
    )
    assert created.status_code == 201
    assert created.json()["code"] == "DTO-1009"

    duplicate = admin_client.post(
        "/api/admin/dto-offices",
        json={"code": "DTO-1009", "name": "Another", "district_id": m.goalpara.id},
    )
    assert duplicate.status_code == 409

    renamed = admin_client.patch(
        f"/api/admin/dto-offices/{created.json()['id']}", json={"name": "DTO Goalpara"}
    )
    assert renamed.json()["name"] == "DTO Goalpara"


def test_bulk_police_stations_adds_new_rows_and_skips_existing(
    admin_client: TestClient, m: Masters
) -> None:
    response = admin_client.post(
        "/api/admin/police-stations/bulk",
        files={
            "file": (
                "stations.csv",
                b"Police Station Name,District ID,District Name\n"
                b"Margherita PS,1022,Tinsukia\n"
                b"Makum PS,1022,Tinsukia\n"
                b"Sonai PS,1004,Cachar\n",
                "text/csv",
            )
        },
    )
    assert response.status_code == 200
    assert response.json() == {"added": 2, "skipped": 1}


def test_bulk_upload_is_all_or_nothing(admin_client: TestClient, m: Masters) -> None:
    response = admin_client.post(
        "/api/admin/police-stations/bulk",
        files={
            "file": (
                "stations.csv",
                b"Police Station Name,District ID\nMakum PS,1022\nGhost PS,9999\n",
                "text/csv",
            )
        },
    )
    assert response.status_code == 400
    assert response.json()["errors"] == ["Row 3: District ID 9999 is not in the district master."]
    names = [s["name"] for s in admin_client.get("/api/admin/police-stations").json()]
    assert "Makum PS" not in names


def test_bulk_districts_and_dto_offices(admin_client: TestClient, m: Masters) -> None:
    districts = admin_client.post(
        "/api/admin/districts/bulk",
        files={
            "file": (
                "d.csv",
                b"District ID,District Name,Short Name\n"
                b"1022,Tinsukia,tinsukia\n1012,Jorhat,jorhat\n",
                "text/csv",
            )
        },
    )
    assert districts.json() == {"added": 1, "skipped": 1}

    offices = admin_client.post(
        "/api/admin/dto-offices/bulk",
        files={
            "file": (
                "o.csv",
                b"DTO Office ID,DTO Office Name,District ID\n"
                b'DTO-1012,"District Transport Office, Jorhat",1012\n',
                "text/csv",
            )
        },
    )
    assert offices.json() == {"added": 1, "skipped": 0}


def test_bulk_upload_rejects_other_file_types(admin_client: TestClient) -> None:
    response = admin_client.post(
        "/api/admin/districts/bulk", files={"file": ("d.txt", b"hello", "text/plain")}
    )
    assert response.status_code == 400
