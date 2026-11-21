from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import (
    admin_form,
    admin_lists,
    admin_masters,
    admin_users,
    auth,
    health,
    officer,
    permits,
    public,
    status,
)
from app.core.config import get_settings
from app.core.dependencies import require_fetch_header
from app.core.errors import DomainError

settings = get_settings()

# Interactive docs are for development only.
app = FastAPI(
    title="Picnic Portal API",
    description="Picnic/Recreational Journey Permit, Transport Department, Government of Assam",
    version="0.5.0",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)


@app.exception_handler(DomainError)
async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    body: dict[str, object] = {"detail": exc.message}
    if exc.errors:
        body["errors"] = exc.errors
    field_errors = getattr(exc, "field_errors", None)
    if field_errors:
        body["field_errors"] = field_errors
    extra = getattr(exc, "extra", None)
    if extra:
        body.update(extra)
    return JSONResponse(status_code=exc.status_code, content=body)


# Every route sits under /api, so the paths are the same behind Nginx and in development.
api_router = APIRouter(prefix="/api", dependencies=[Depends(require_fetch_header)])
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(public.router)
api_router.include_router(status.router)
api_router.include_router(admin_masters.router)
api_router.include_router(admin_users.router)
api_router.include_router(admin_form.router)
api_router.include_router(admin_lists.router)
api_router.include_router(officer.router)
api_router.include_router(permits.router)

app.include_router(api_router)
