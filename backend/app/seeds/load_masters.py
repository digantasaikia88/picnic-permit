"""Load the masters and the first officer accounts from the CSV files.

    docker compose exec backend python -m app.seeds.load_masters

Reads District_Master.csv, Police_Stations_master.csv, DTO_Office_Master.csv
and User_ID_List.csv from MASTERS_DIR. Safe to run again: rows that already
exist are skipped.

The accounts are created without a password. A State Admin issues the first
passwords from the portal ("Generate passwords"), as a one-time Excel download.
"""

import sys
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.errors import DomainError
from app.models import District, DtoOffice, PoliceStation, Role, User
from app.services import audit, masters, spreadsheets, users
from app.services.users import OfficeLink

USER_COLUMNS = ["User ID", "Role", "Office Name", "District ID"]

_ROLES = {"DTO": Role.DTO, "DC Office": Role.DC_OFFICE, "Police Station": Role.POLICE_STATION}


def _read(folder: Path, name: str, columns: list[str]) -> list[dict[str, str]]:
    path = folder / name
    if not path.is_file():
        raise DomainError(f"File not found: {path}")
    rows = spreadsheets.read_table(name, path.read_bytes())
    spreadsheets.require_columns(rows, columns)
    return rows


def import_seed_users(db: Session, rows: list[dict[str, str]]) -> tuple[int, int]:
    """Create the officer accounts of User_ID_List.csv, with the user IDs given there."""
    errors: list[str] = []
    plans: list[tuple[str, Role, OfficeLink]] = []
    skipped = 0

    for row_number, row in enumerate(rows, start=2):
        user_id = row["User ID"].strip().lower()
        role = _ROLES.get(row["Role"])
        if role is None:
            errors.append(f"Row {row_number}: unknown role '{row['Role']}'.")
            continue
        try:
            district = db.scalar(select(District).where(District.code == int(row["District ID"])))
        except ValueError:
            district = None
        if district is None:
            errors.append(f"Row {row_number}: District ID '{row['District ID']}' is not known.")
            continue

        if db.scalar(select(User.id).where(User.user_id == user_id)) is not None:
            skipped += 1
            continue

        if role == Role.DTO:
            office = db.scalar(select(DtoOffice).where(DtoOffice.district_id == district.id))
            if office is None:
                errors.append(f"Row {row_number}: no DTO office for {district.name}.")
                continue
            link = OfficeLink(dto_office=office)
        elif role == Role.POLICE_STATION:
            station = db.scalar(
                select(PoliceStation).where(
                    PoliceStation.district_id == district.id,
                    func.lower(PoliceStation.name) == row["Office Name"].lower(),
                )
            )
            if station is None:
                errors.append(
                    f"Row {row_number}: police station '{row['Office Name']}' "
                    f"is not in {district.name}."
                )
                continue
            link = OfficeLink(police_station=station)
        else:
            link = OfficeLink(district=district)
        plans.append((user_id, role, link))

    if errors:
        raise DomainError(f"The user list has {len(errors)} problem(s).", errors=errors)

    for user_id, role, link in plans:
        users.create_user(
            db,
            None,
            role=role,
            link=link,
            user_id=user_id,
            with_password=False,
            system_label=audit.SYSTEM_SEED,
        )
    return len(plans), skipped


def load_all(db: Session, folder: Path) -> dict[str, tuple[int, int]]:
    """Load every master file. Returns {name: (added, skipped)}. Does not commit."""
    seed = audit.SYSTEM_SEED
    return {
        "Districts": masters.import_districts(
            db,
            None,
            _read(folder, "District_Master.csv", masters.DISTRICT_COLUMNS),
            system_label=seed,
        ),
        "Police stations": masters.import_police_stations(
            db,
            None,
            _read(folder, "Police_Stations_master.csv", masters.POLICE_STATION_COLUMNS),
            system_label=seed,
        ),
        "DTO offices": masters.import_dto_offices(
            db,
            None,
            _read(folder, "DTO_Office_Master.csv", masters.DTO_OFFICE_COLUMNS),
            system_label=seed,
        ),
        "Officer accounts": import_seed_users(db, _read(folder, "User_ID_List.csv", USER_COLUMNS)),
    }


def main() -> int:
    folder = Path(get_settings().masters_dir)
    with SessionLocal() as db:
        try:
            result = load_all(db, folder)
        except DomainError as exc:
            db.rollback()
            print(f"FAILED: {exc.message}", file=sys.stderr)
            for line in exc.errors:
                print(f"  {line}", file=sys.stderr)
            return 1
        db.commit()

    print(f"Loaded masters from {folder}")
    for name, (added, skipped) in result.items():
        print(f"  {name:<18} added {added:>4}, already present {skipped:>4}")
    print("Officer accounts have no password yet. A State Admin issues them from the portal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
