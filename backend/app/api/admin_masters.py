"""State Admin: districts, police stations and DTO offices."""

from fastapi import APIRouter, Depends, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_state_admin
from app.models import User
from app.schemas.masters import (
    BulkImportResult,
    DistrictCreate,
    DistrictOut,
    DistrictUpdate,
    DtoOfficeCreate,
    DtoOfficeOut,
    DtoOfficeUpdate,
    PoliceStationCreate,
    PoliceStationOut,
    PoliceStationUpdate,
)
from app.services import masters, spreadsheets

router = APIRouter(prefix="/admin", tags=["admin: masters"])


async def _rows(file: UploadFile, columns: list[str]) -> list[dict[str, str]]:
    content = await file.read(spreadsheets.MAX_UPLOAD_BYTES + 1)
    rows = spreadsheets.read_table(file.filename or "", content)
    spreadsheets.require_columns(rows, columns)
    return rows


# ---------------------------------------------------------------- districts


@router.get("/districts", response_model=list[DistrictOut])
def list_districts(
    db: Session = Depends(get_db), _: User = Depends(require_state_admin)
) -> list[DistrictOut]:
    return masters.list_districts(db)


@router.post("/districts", response_model=DistrictOut, status_code=status.HTTP_201_CREATED)
def create_district(
    body: DistrictCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> DistrictOut:
    district = masters.create_district(
        db, admin, code=body.code, name=body.name, short_name=body.short_name
    )
    db.commit()
    return district


@router.patch("/districts/{district_id}", response_model=DistrictOut)
def update_district(
    district_id: int,
    body: DistrictUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> DistrictOut:
    district = masters.update_district(
        db, admin, district_id, **body.model_dump(exclude_unset=True)
    )
    db.commit()
    return district


@router.delete("/districts/{district_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_district(
    district_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> None:
    masters.delete_district(db, admin, district_id)
    db.commit()


@router.post("/districts/bulk", response_model=BulkImportResult)
async def bulk_districts(
    file: UploadFile,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> BulkImportResult:
    rows = await _rows(file, masters.DISTRICT_COLUMNS)
    added, skipped = masters.import_districts(db, admin, rows)
    db.commit()
    return BulkImportResult(added=added, skipped=skipped)


# ---------------------------------------------------------- police stations


@router.get("/police-stations", response_model=list[PoliceStationOut])
def list_police_stations(
    district_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_state_admin),
) -> list[PoliceStationOut]:
    return masters.list_police_stations(db, district_id=district_id)


@router.post(
    "/police-stations", response_model=PoliceStationOut, status_code=status.HTTP_201_CREATED
)
def create_police_station(
    body: PoliceStationCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> PoliceStationOut:
    station = masters.create_police_station(db, admin, name=body.name, district_id=body.district_id)
    db.commit()
    return station


@router.patch("/police-stations/{station_id}", response_model=PoliceStationOut)
def update_police_station(
    station_id: int,
    body: PoliceStationUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> PoliceStationOut:
    station = masters.update_police_station(
        db, admin, station_id, **body.model_dump(exclude_unset=True)
    )
    db.commit()
    return station


@router.delete("/police-stations/{station_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_police_station(
    station_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> None:
    masters.delete_police_station(db, admin, station_id)
    db.commit()


@router.post("/police-stations/bulk", response_model=BulkImportResult)
async def bulk_police_stations(
    file: UploadFile,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> BulkImportResult:
    rows = await _rows(file, masters.POLICE_STATION_COLUMNS)
    added, skipped = masters.import_police_stations(db, admin, rows)
    db.commit()
    return BulkImportResult(added=added, skipped=skipped)


# -------------------------------------------------------------- DTO offices


@router.get("/dto-offices", response_model=list[DtoOfficeOut])
def list_dto_offices(
    district_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_state_admin),
) -> list[DtoOfficeOut]:
    return masters.list_dto_offices(db, district_id=district_id)


@router.post("/dto-offices", response_model=DtoOfficeOut, status_code=status.HTTP_201_CREATED)
def create_dto_office(
    body: DtoOfficeCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> DtoOfficeOut:
    office = masters.create_dto_office(
        db, admin, code=body.code, name=body.name, district_id=body.district_id
    )
    db.commit()
    return office


@router.patch("/dto-offices/{office_id}", response_model=DtoOfficeOut)
def update_dto_office(
    office_id: int,
    body: DtoOfficeUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> DtoOfficeOut:
    office = masters.update_dto_office(db, admin, office_id, **body.model_dump(exclude_unset=True))
    db.commit()
    return office


@router.delete("/dto-offices/{office_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dto_office(
    office_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> None:
    masters.delete_dto_office(db, admin, office_id)
    db.commit()


@router.post("/dto-offices/bulk", response_model=BulkImportResult)
async def bulk_dto_offices(
    file: UploadFile,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> BulkImportResult:
    rows = await _rows(file, masters.DTO_OFFICE_COLUMNS)
    added, skipped = masters.import_dto_offices(db, admin, rows)
    db.commit()
    return BulkImportResult(added=added, skipped=skipped)
