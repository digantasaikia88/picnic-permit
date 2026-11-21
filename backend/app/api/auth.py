from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.dependencies import SESSION_COOKIE, CurrentSession, get_current_session
from app.schemas.auth import CaptchaResponse, ChangePasswordRequest, LoginRequest, MeResponse
from app.services import auth, captcha

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/captcha", response_model=CaptchaResponse, summary="New login captcha")
def new_captcha(
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CaptchaResponse:
    response.headers["Cache-Control"] = "no-store"
    if not settings.captcha_enabled:
        return CaptchaResponse(enabled=False)
    captcha_id, _answer, image = captcha.create(db)
    db.commit()
    return CaptchaResponse(enabled=True, captcha_id=captcha_id, image=image)


@router.post("/login", response_model=MeResponse, summary="Officer login")
def login(
    body: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> MeResponse:
    user, token, max_age = auth.login(
        db,
        user_id=body.user_id,
        password=body.password,
        captcha_id=body.captcha_id,
        captcha_answer=body.captcha_answer,
    )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        path="/",
    )
    return MeResponse.from_user(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Log out")
def logout(
    response: Response,
    current: CurrentSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> None:
    auth.logout(db, current.session)
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=MeResponse, summary="The logged-in officer")
def me(current: CurrentSession = Depends(get_current_session)) -> MeResponse:
    return MeResponse.from_user(current.user)


@router.post(
    "/change-password", status_code=status.HTTP_204_NO_CONTENT, summary="Change own password"
)
def change_password(
    body: ChangePasswordRequest,
    current: CurrentSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> None:
    auth.change_password(
        db,
        user=current.user,
        session=current.session,
        current_password=body.current_password,
        new_password=body.new_password,
    )
    db.commit()
