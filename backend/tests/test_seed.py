from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AuditLog, District, DtoOffice, PoliceStation, Role, User
from app.seeds.load_masters import load_all

MASTERS_DIR = Path(get_settings().masters_dir)


def _count(db: Session, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def test_seed_loads_all_masters_and_376_officers_and_can_run_twice(db: Session) -> None:
    first = load_all(db, MASTERS_DIR)
    db.commit()

    assert first == {
        "Districts": (35, 0),
        "Police stations": (306, 0),
        "DTO offices": (35, 0),
        "Officer accounts": (376, 0),
    }
    assert _count(db, District) == 35
    assert _count(db, PoliceStation) == 306
    assert _count(db, DtoOffice) == 35
    assert _count(db, User) == 376

    by_role = dict(db.execute(select(User.role, func.count()).group_by(User.role)).all())
    assert by_role == {Role.DTO: 35, Role.DC_OFFICE: 35, Role.POLICE_STATION: 306}

    second = load_all(db, MASTERS_DIR)
    assert second == {
        "Districts": (0, 35),
        "Police stations": (0, 306),
        "DTO offices": (0, 35),
        "Officer accounts": (0, 376),
    }
    assert _count(db, User) == 376


def test_seeded_officers_have_no_password_and_are_linked_by_internal_id(db: Session) -> None:
    load_all(db, MASTERS_DIR)

    assert (
        db.scalar(select(func.count()).select_from(User).where(User.password_hash.is_not(None)))
        == 0
    )

    dto = db.scalar(select(User).where(User.user_id == "dto.kamrupm"))
    assert dto.dto_office.district.name == "Kamrup Metropolitan"
    assert dto.office_label == "District Transport Office, Kamrup Metropolitan"

    dc = db.scalar(select(User).where(User.user_id == "dc.salmara"))
    assert dc.district.name == "South Salmara Mankachar"
    assert dc.office_label == "DC Office, South Salmara Mankachar"

    ps = db.scalar(select(User).where(User.user_id == "ps.goalpara"))
    assert ps.police_station.name == "Goalpara PS"
    assert ps.police_station.district.name == "Goalpara"


def test_seed_writes_audit_rows_as_the_system(db: Session) -> None:
    load_all(db, MASTERS_DIR)
    db.flush()
    labels = set(db.scalars(select(AuditLog.actor_label).distinct()))
    assert labels == {"system:seed"}
    assert _count(db, AuditLog) == 35 + 306 + 35 + 376
