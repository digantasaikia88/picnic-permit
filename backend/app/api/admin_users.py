"""State Admin: officer accounts, settings and the audit log."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_state_admin
from app.models import AuditLog, Role, User
from app.schemas.users import (
    AuditList,
    AuditOut,
    PendingPasswords,
    SettingOut,
    SettingUpdate,
    SuggestedUserId,
    UserCreate,
    UserList,
    UserOut,
    UserUpdate,
    UserWithPassword,
)
from app.services import settings as app_settings
from app.services import spreadsheets, users

router = APIRouter(prefix="/admin", tags=["admin: users"])


def _xlsx_download(content: bytes, name: str) -> Response:
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return Response(
        content=content,
        media_type=spreadsheets.XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{name}_{stamp}.xlsx"',
            # Holds passwords: must never be kept by a browser or proxy cache.
            "Cache-Control": "no-store",
        },
    )


@router.get("/users", response_model=UserList)
def list_users(
    role: Role | None = None,
    district_id: int | None = None,
    search: str | None = Query(default=None, max_length=64),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_state_admin),
) -> UserList:
    rows, total = users.list_users(
        db, role=role, district_id=district_id, search=search, page=page, page_size=page_size
    )
    return UserList(
        items=[UserOut.from_user(u) for u in rows], total=total, page=page, page_size=page_size
    )


@router.get("/users/suggest-id", response_model=SuggestedUserId)
def suggest_user_id(
    role: Role,
    district_id: int | None = None,
    police_station_id: int | None = None,
    dto_office_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_state_admin),
) -> SuggestedUserId:
    link = users.resolve_office(
        db,
        role,
        district_id=district_id,
        police_station_id=police_station_id,
        dto_office_id=dto_office_id,
    )
    return SuggestedUserId(user_id=users.suggest_for(db, role, link))


@router.get("/users/pending-passwords", response_model=PendingPasswords)
def pending_passwords(
    db: Session = Depends(get_db), _: User = Depends(require_state_admin)
) -> PendingPasswords:
    return PendingPasswords(**users.count_pending_first_passwords(db))


@router.post("/users/generate-passwords", summary="Issue first passwords, as an Excel download")
def generate_passwords(
    include_never_logged_in: bool = False,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> Response:
    issued = users.generate_first_passwords(
        db, admin, include_never_logged_in=include_never_logged_in
    )
    content = spreadsheets.write_xlsx(
        users.CREDENTIALS_HEADERS, users.credentials_rows(issued), sheet_title="Passwords"
    )
    db.commit()
    return _xlsx_download(content, "picnic_portal_passwords")


@router.get("/users/bulk-template", summary="Empty list for bulk user creation")
def bulk_template(_: User = Depends(require_state_admin)) -> Response:
    content = spreadsheets.write_xlsx(
        [*users.BULK_COLUMNS, "User ID"],
        [
            ["DTO", 1022, "", ""],
            ["DC Office", 1022, "", ""],
            ["Police Station", 1022, "Margherita PS", ""],
            ["Viewer", 1022, "", "sp.tinsukia"],
            ["Viewer", "", "", "transport.state.1"],
        ],
        sheet_title="Users",
    )
    return Response(
        content=content,
        media_type=spreadsheets.XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": 'attachment; filename="bulk_users_template.xlsx"'},
    )


@router.post("/users/bulk", summary="Create users from a list, returned with passwords")
async def bulk_create(
    file: UploadFile,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> Response:
    content = await file.read(spreadsheets.MAX_UPLOAD_BYTES + 1)
    rows = spreadsheets.read_table(file.filename or "", content)
    spreadsheets.require_columns(rows, users.BULK_COLUMNS)
    created = users.bulk_create(db, admin, rows)
    workbook = spreadsheets.write_xlsx(
        users.CREDENTIALS_HEADERS, users.credentials_rows(created), sheet_title="New users"
    )
    db.commit()
    return _xlsx_download(workbook, "picnic_portal_new_users")


@router.post("/users", response_model=UserWithPassword, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    response: Response,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> UserWithPassword:
    link = users.resolve_office(
        db,
        body.role,
        district_id=body.district_id,
        police_station_id=body.police_station_id,
        dto_office_id=body.dto_office_id,
    )
    user, password = users.create_user(
        db, admin, role=body.role, link=link, user_id=body.user_id, office_name=body.office_name
    )
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return UserWithPassword(user=UserOut.from_user(user), password=password or "")


@router.patch("/users/{user_pk}", response_model=UserOut)
def update_user(
    user_pk: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> UserOut:
    user = users.update_user(db, admin, user_pk, **body.model_dump(exclude_unset=True))
    db.commit()
    return UserOut.from_user(user)


@router.post("/users/{user_pk}/reset-password", response_model=UserWithPassword)
def reset_password(
    user_pk: int,
    response: Response,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> UserWithPassword:
    user, password = users.reset_password(db, admin, user_pk)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return UserWithPassword(user=UserOut.from_user(user), password=password)


# ------------------------------------------------------------------ settings


@router.get("/settings", response_model=list[SettingOut], tags=["admin: settings"])
def list_settings(
    db: Session = Depends(get_db), _: User = Depends(require_state_admin)
) -> list[SettingOut]:
    return app_settings.list_settings(db)


@router.patch("/settings/{key}", response_model=SettingOut, tags=["admin: settings"])
def update_setting(
    key: str,
    body: SettingUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_state_admin),
) -> SettingOut:
    setting = app_settings.update_setting(db, admin, key, body.value)
    db.commit()
    return setting


# ----------------------------------------------------------------- audit log


@router.get("/audit-log", response_model=AuditList, tags=["admin: audit log"])
def audit_log(
    entity_type: str | None = Query(default=None, max_length=40),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_state_admin),
) -> AuditList:
    statement = select(AuditLog)
    if entity_type:
        statement = statement.where(AuditLog.entity_type == entity_type)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.scalars(
        statement.order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return AuditList(
        items=[AuditOut.from_row(r) for r in rows], total=total, page=page, page_size=page_size
    )
