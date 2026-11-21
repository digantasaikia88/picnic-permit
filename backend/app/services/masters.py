"""Districts, police stations and DTO offices: add, modify, deactivate, bulk add.

A master row that is in use is never deleted. It is made inactive instead,
which removes it from the dropdowns and keeps old records intact.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, DomainError, NotFoundError
from app.models import District, DtoOffice, PoliceStation, User
from app.services import audit
from app.services.user_ids import is_valid_short_name

# Column names of the bulk upload files. They match the files in docs/masters.
DISTRICT_COLUMNS = ["District ID", "District Name", "Short Name"]
POLICE_STATION_COLUMNS = ["Police Station Name", "District ID"]
DTO_OFFICE_COLUMNS = ["DTO Office ID", "DTO Office Name", "District ID"]


def _clean_name(value: str, what: str) -> str:
    name = " ".join(value.split())
    if not name:
        raise DomainError(f"Enter the {what}.")
    return name


# ---------------------------------------------------------------- districts


def _district_dict(d: District) -> dict:
    return {"code": d.code, "name": d.name, "short_name": d.short_name, "is_active": d.is_active}


def list_districts(db: Session, *, active_only: bool = False) -> list[District]:
    statement = select(District).order_by(District.name)
    if active_only:
        statement = statement.where(District.is_active)
    return list(db.scalars(statement))


def get_district(db: Session, district_id: int) -> District:
    district = db.get(District, district_id)
    if district is None:
        raise NotFoundError("District not found.")
    return district


def _check_district_unique(
    db: Session, *, code: int, name: str, short_name: str, ignore_id: int | None = None
) -> None:
    def taken(condition) -> bool:
        statement = select(District.id).where(condition)
        if ignore_id is not None:
            statement = statement.where(District.id != ignore_id)
        return db.scalar(statement) is not None

    if taken(District.code == code):
        raise ConflictError(f"District ID {code} is already in use.")
    if taken(func.lower(District.name) == name.lower()):
        raise ConflictError(f"A district named {name} already exists.")
    if taken(District.short_name == short_name):
        raise ConflictError(f"The short name {short_name} is already in use.")


def _clean_short_name(short_name: str) -> str:
    short_name = short_name.strip().lower()
    if not is_valid_short_name(short_name):
        raise DomainError(
            "The short name may contain only lowercase letters and digits, with no spaces."
        )
    return short_name


def create_district(
    db: Session,
    actor: User | None,
    *,
    code: int,
    name: str,
    short_name: str,
    system_label: str = audit.SYSTEM_CLI,
) -> District:
    if code <= 0:
        raise DomainError("The District ID must be a positive whole number.")
    name = _clean_name(name, "district name")
    short_name = _clean_short_name(short_name)
    _check_district_unique(db, code=code, name=name, short_name=short_name)

    district = District(code=code, name=name, short_name=short_name)
    db.add(district)
    db.flush()
    audit.record(
        db,
        actor=actor,
        system_label=system_label,
        action="district.create",
        entity_type="district",
        entity_id=district.id,
        entity_label=district.name,
        new=_district_dict(district),
    )
    return district


def update_district(
    db: Session,
    actor: User,
    district_id: int,
    *,
    code: int | None = None,
    name: str | None = None,
    short_name: str | None = None,
    is_active: bool | None = None,
) -> District:
    district = get_district(db, district_id)
    before = _district_dict(district)

    new_code = district.code if code is None else code
    new_name = district.name if name is None else _clean_name(name, "district name")
    new_short = district.short_name if short_name is None else _clean_short_name(short_name)
    if new_code <= 0:
        raise DomainError("The District ID must be a positive whole number.")
    _check_district_unique(
        db, code=new_code, name=new_name, short_name=new_short, ignore_id=district.id
    )

    district.code, district.name, district.short_name = new_code, new_name, new_short
    if is_active is not None:
        district.is_active = is_active

    old, new = audit.changed_fields(before, _district_dict(district))
    if new:
        audit.record(
            db,
            actor=actor,
            action="district.update",
            entity_type="district",
            entity_id=district.id,
            entity_label=district.name,
            old=old,
            new=new,
        )
    return district


def delete_district(db: Session, actor: User, district_id: int) -> None:
    district = get_district(db, district_id)
    in_use = (
        db.scalar(select(PoliceStation.id).where(PoliceStation.district_id == district.id).limit(1))
        or db.scalar(select(DtoOffice.id).where(DtoOffice.district_id == district.id).limit(1))
        or db.scalar(select(User.id).where(User.district_id == district.id).limit(1))
    )
    if in_use:
        raise ConflictError(
            "This district is in use and cannot be deleted. Make it inactive instead."
        )
    audit.record(
        db,
        actor=actor,
        action="district.delete",
        entity_type="district",
        entity_id=district.id,
        entity_label=district.name,
        old=_district_dict(district),
    )
    db.delete(district)


# ---------------------------------------------------------- police stations


def _station_dict(s: PoliceStation) -> dict:
    return {"name": s.name, "district_id": s.district_id, "is_active": s.is_active}


def list_police_stations(
    db: Session, *, district_id: int | None = None, active_only: bool = False
) -> list[PoliceStation]:
    statement = select(PoliceStation).order_by(PoliceStation.name)
    if district_id is not None:
        statement = statement.where(PoliceStation.district_id == district_id)
    if active_only:
        statement = statement.where(PoliceStation.is_active)
    return list(db.scalars(statement))


def get_police_station(db: Session, station_id: int) -> PoliceStation:
    station = db.get(PoliceStation, station_id)
    if station is None:
        raise NotFoundError("Police station not found.")
    return station


def _check_station_unique(
    db: Session, *, name: str, district: District, ignore_id: int | None = None
) -> None:
    statement = select(PoliceStation.id).where(
        PoliceStation.district_id == district.id, func.lower(PoliceStation.name) == name.lower()
    )
    if ignore_id is not None:
        statement = statement.where(PoliceStation.id != ignore_id)
    if db.scalar(statement) is not None:
        raise ConflictError(f"{name} already exists in {district.name}.")


def create_police_station(
    db: Session,
    actor: User | None,
    *,
    name: str,
    district_id: int,
    system_label: str = audit.SYSTEM_CLI,
) -> PoliceStation:
    name = _clean_name(name, "police station name")
    district = get_district(db, district_id)
    _check_station_unique(db, name=name, district=district)

    station = PoliceStation(name=name, district_id=district.id)
    db.add(station)
    db.flush()
    audit.record(
        db,
        actor=actor,
        system_label=system_label,
        action="police_station.create",
        entity_type="police_station",
        entity_id=station.id,
        entity_label=station.name,
        new=_station_dict(station),
    )
    return station


def update_police_station(
    db: Session,
    actor: User,
    station_id: int,
    *,
    name: str | None = None,
    district_id: int | None = None,
    is_active: bool | None = None,
) -> PoliceStation:
    station = get_police_station(db, station_id)
    before = _station_dict(station)

    new_name = station.name if name is None else _clean_name(name, "police station name")
    new_district = station.district if district_id is None else get_district(db, district_id)
    _check_station_unique(db, name=new_name, district=new_district, ignore_id=station.id)

    station.name = new_name
    station.district_id = new_district.id
    if is_active is not None:
        station.is_active = is_active

    old, new = audit.changed_fields(before, _station_dict(station))
    if new:
        audit.record(
            db,
            actor=actor,
            action="police_station.update",
            entity_type="police_station",
            entity_id=station.id,
            entity_label=station.name,
            old=old,
            new=new,
        )
    db.flush()
    db.refresh(station)
    return station


def delete_police_station(db: Session, actor: User, station_id: int) -> None:
    station = get_police_station(db, station_id)
    if db.scalar(select(User.id).where(User.police_station_id == station.id).limit(1)):
        raise ConflictError(
            "This police station is in use and cannot be deleted. Make it inactive instead."
        )
    audit.record(
        db,
        actor=actor,
        action="police_station.delete",
        entity_type="police_station",
        entity_id=station.id,
        entity_label=station.name,
        old=_station_dict(station),
    )
    db.delete(station)


# -------------------------------------------------------------- DTO offices


def _dto_dict(o: DtoOffice) -> dict:
    return {
        "code": o.code,
        "name": o.name,
        "district_id": o.district_id,
        "is_active": o.is_active,
    }


def list_dto_offices(
    db: Session, *, district_id: int | None = None, active_only: bool = False
) -> list[DtoOffice]:
    statement = select(DtoOffice).order_by(DtoOffice.name)
    if district_id is not None:
        statement = statement.where(DtoOffice.district_id == district_id)
    if active_only:
        statement = statement.where(DtoOffice.is_active)
    return list(db.scalars(statement))


def get_dto_office(db: Session, office_id: int) -> DtoOffice:
    office = db.get(DtoOffice, office_id)
    if office is None:
        raise NotFoundError("DTO office not found.")
    return office


def _clean_dto_code(code: str) -> str:
    code = code.strip().upper()
    if not code or len(code) > 30 or " " in code:
        raise DomainError("Enter the DTO Office ID without spaces, for example DTO-1022.")
    return code


def _check_dto_code_unique(db: Session, code: str, ignore_id: int | None = None) -> None:
    statement = select(DtoOffice.id).where(DtoOffice.code == code)
    if ignore_id is not None:
        statement = statement.where(DtoOffice.id != ignore_id)
    if db.scalar(statement) is not None:
        raise ConflictError(f"DTO Office ID {code} is already in use.")


def create_dto_office(
    db: Session,
    actor: User | None,
    *,
    code: str,
    name: str,
    district_id: int,
    system_label: str = audit.SYSTEM_CLI,
) -> DtoOffice:
    code = _clean_dto_code(code)
    name = _clean_name(name, "DTO office name")
    district = get_district(db, district_id)
    _check_dto_code_unique(db, code)

    office = DtoOffice(code=code, name=name, district_id=district.id)
    db.add(office)
    db.flush()
    audit.record(
        db,
        actor=actor,
        system_label=system_label,
        action="dto_office.create",
        entity_type="dto_office",
        entity_id=office.id,
        entity_label=office.name,
        new=_dto_dict(office),
    )
    return office


def update_dto_office(
    db: Session,
    actor: User,
    office_id: int,
    *,
    code: str | None = None,
    name: str | None = None,
    district_id: int | None = None,
    is_active: bool | None = None,
) -> DtoOffice:
    office = get_dto_office(db, office_id)
    before = _dto_dict(office)

    if code is not None:
        new_code = _clean_dto_code(code)
        _check_dto_code_unique(db, new_code, ignore_id=office.id)
        office.code = new_code
    if name is not None:
        office.name = _clean_name(name, "DTO office name")
    if district_id is not None:
        office.district_id = get_district(db, district_id).id
    if is_active is not None:
        office.is_active = is_active

    old, new = audit.changed_fields(before, _dto_dict(office))
    if new:
        audit.record(
            db,
            actor=actor,
            action="dto_office.update",
            entity_type="dto_office",
            entity_id=office.id,
            entity_label=office.name,
            old=old,
            new=new,
        )
    db.flush()
    db.refresh(office)
    return office


def delete_dto_office(db: Session, actor: User, office_id: int) -> None:
    office = get_dto_office(db, office_id)
    if db.scalar(select(User.id).where(User.dto_office_id == office.id).limit(1)):
        raise ConflictError(
            "This DTO office is in use and cannot be deleted. Make it inactive instead."
        )
    audit.record(
        db,
        actor=actor,
        action="dto_office.delete",
        entity_type="dto_office",
        entity_id=office.id,
        entity_label=office.name,
        old=_dto_dict(office),
    )
    db.delete(office)


# -------------------------------------------------------------- bulk import
#
# All or nothing: every row is checked first, and if any row has a problem
# nothing is added. Rows that already exist are skipped, so a file can be
# loaded twice safely. Each function returns (added, skipped).


def _district_by_code(db: Session, raw: str, row_number: int, errors: list[str]) -> District | None:
    try:
        code = int(raw)
    except ValueError:
        errors.append(f"Row {row_number}: District ID '{raw}' is not a whole number.")
        return None
    district = db.scalar(select(District).where(District.code == code))
    if district is None:
        errors.append(f"Row {row_number}: District ID {code} is not in the district master.")
    return district


def _fail_if_errors(errors: list[str]) -> None:
    if errors:
        raise DomainError(
            f"Nothing was added. The file has {len(errors)} problem(s).", errors=errors[:100]
        )


def import_districts(
    db: Session,
    actor: User | None,
    rows: list[dict[str, str]],
    *,
    system_label: str = audit.SYSTEM_CLI,
) -> tuple[int, int]:
    errors: list[str] = []
    pending: list[tuple[int, str, str]] = []
    skipped = 0
    seen_codes: set[int] = set()

    for row_number, row in enumerate(rows, start=2):
        try:
            code = int(row["District ID"])
        except ValueError:
            errors.append(f"Row {row_number}: District ID is not a whole number.")
            continue
        if code in seen_codes:
            errors.append(f"Row {row_number}: District ID {code} is repeated in the file.")
            continue
        seen_codes.add(code)
        if db.scalar(select(District.id).where(District.code == code)) is not None:
            skipped += 1
            continue
        pending.append((code, row["District Name"], row["Short Name"]))

    _fail_if_errors(errors)
    for index, (code, name, short_name) in enumerate(pending):
        try:
            create_district(
                db, actor, code=code, name=name, short_name=short_name, system_label=system_label
            )
        except DomainError as exc:
            errors.append(f"District ID {pending[index][0]}: {exc.message}")
    _fail_if_errors(errors)
    return len(pending), skipped


def import_police_stations(
    db: Session,
    actor: User | None,
    rows: list[dict[str, str]],
    *,
    system_label: str = audit.SYSTEM_CLI,
) -> tuple[int, int]:
    errors: list[str] = []
    pending: list[tuple[str, District]] = []
    skipped = 0
    seen: set[tuple[int, str]] = set()

    for row_number, row in enumerate(rows, start=2):
        name = " ".join(row["Police Station Name"].split())
        if not name:
            errors.append(f"Row {row_number}: Police Station Name is empty.")
            continue
        district = _district_by_code(db, row["District ID"], row_number, errors)
        if district is None:
            continue
        key = (district.id, name.lower())
        if key in seen:
            errors.append(f"Row {row_number}: {name} is repeated in the file.")
            continue
        seen.add(key)
        exists = db.scalar(
            select(PoliceStation.id).where(
                PoliceStation.district_id == district.id,
                func.lower(PoliceStation.name) == name.lower(),
            )
        )
        if exists is not None:
            skipped += 1
            continue
        pending.append((name, district))

    _fail_if_errors(errors)
    for name, district in pending:
        create_police_station(
            db, actor, name=name, district_id=district.id, system_label=system_label
        )
    return len(pending), skipped


def import_dto_offices(
    db: Session,
    actor: User | None,
    rows: list[dict[str, str]],
    *,
    system_label: str = audit.SYSTEM_CLI,
) -> tuple[int, int]:
    errors: list[str] = []
    pending: list[tuple[str, str, District]] = []
    skipped = 0
    seen: set[str] = set()

    for row_number, row in enumerate(rows, start=2):
        code = row["DTO Office ID"].strip().upper()
        name = " ".join(row["DTO Office Name"].split())
        if not code or not name:
            errors.append(f"Row {row_number}: DTO Office ID and DTO Office Name are both needed.")
            continue
        district = _district_by_code(db, row["District ID"], row_number, errors)
        if district is None:
            continue
        if code in seen:
            errors.append(f"Row {row_number}: {code} is repeated in the file.")
            continue
        seen.add(code)
        if db.scalar(select(DtoOffice.id).where(DtoOffice.code == code)) is not None:
            skipped += 1
            continue
        pending.append((code, name, district))

    _fail_if_errors(errors)
    for code, name, district in pending:
        create_dto_office(
            db, actor, code=code, name=name, district_id=district.id, system_label=system_label
        )
    return len(pending), skipped
