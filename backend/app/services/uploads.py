"""Uploaded files: PDF, JPG and PNG only, size-limited, stored under random names.

A file chosen in the form is kept as a temporary upload. On submission it
becomes a document of the application. Temporary uploads that are never
submitted are deleted when they expire.
"""

import io
import logging
import secrets
import uuid
from datetime import timedelta
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import DomainError, NotFoundError
from app.core.timeutil import now_utc
from app.models import Application, ApplicationDocument, DocType, TempUpload
from app.services import settings as app_settings

logger = logging.getLogger(__name__)

_TEMP = "tmp"
_FINAL = "applications"


def _folder(name: str) -> Path:
    path = Path(get_settings().upload_dir) / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def temp_path(upload: TempUpload) -> Path:
    return _folder(_TEMP) / upload.stored_name


def document_path(document: ApplicationDocument) -> Path:
    return _folder(_FINAL) / document.stored_name


def max_bytes(db: Session) -> int:
    return app_settings.get_int(db, app_settings.UPLOAD_MAX_MB) * 1024 * 1024


def sniff(content: bytes) -> tuple[str, str]:
    """Work out the file type from its content, not its name.

    Returns (content type, file extension). Anything that is not a real PDF,
    JPEG or PNG is refused.
    """
    if content.startswith(b"%PDF-"):
        return "application/pdf", "pdf"

    if content.startswith(b"\xff\xd8\xff"):
        kind = ("image/jpeg", "jpg", "JPEG")
    elif content.startswith(b"\x89PNG\r\n\x1a\n"):
        kind = ("image/png", "png", "PNG")
    else:
        raise DomainError("Only PDF, JPG and PNG files can be uploaded.")

    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.format != kind[2]:
                raise DomainError("Only PDF, JPG and PNG files can be uploaded.")
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise DomainError("This picture could not be read. Please upload it again.") from exc
    return kind[0], kind[1]


def purge_expired(db: Session) -> int:
    """Delete temporary uploads whose time has run out. Returns how many."""
    expired = list(db.scalars(select(TempUpload).where(TempUpload.expires_at < now_utc())))
    for upload in expired:
        temp_path(upload).unlink(missing_ok=True)
        db.delete(upload)
    return len(expired)


def save_temp(db: Session, *, filename: str, content: bytes, doc_type: DocType) -> TempUpload:
    limit = max_bytes(db)
    if not content:
        raise DomainError("The file is empty.")
    if len(content) > limit:
        raise DomainError(f"The file is larger than {limit // (1024 * 1024)} MB.")
    content_type, extension = sniff(content)

    purge_expired(db)

    hours = app_settings.get_int(db, app_settings.TEMP_UPLOAD_HOURS)
    upload = TempUpload(
        token=str(uuid.uuid4()),
        doc_type=doc_type,
        stored_name=f"{secrets.token_hex(24)}.{extension}",
        # Kept only to show the applicant what they chose. Never used as a path.
        original_name=Path(filename or "file").name[:255],
        content_type=content_type,
        size_bytes=len(content),
        expires_at=now_utc() + timedelta(hours=hours),
    )
    temp_path(upload).write_bytes(content)
    db.add(upload)
    db.flush()
    return upload


def get_temp(db: Session, token: str) -> TempUpload | None:
    upload = db.get(TempUpload, token)
    if upload is None or upload.expires_at < now_utc():
        return None
    return upload


def delete_temp(db: Session, token: str) -> None:
    upload = db.get(TempUpload, token)
    if upload is None:
        raise NotFoundError("File not found.")
    temp_path(upload).unlink(missing_ok=True)
    db.delete(upload)


def attach(db: Session, application: Application, uploads: dict[DocType, TempUpload]) -> None:
    """Turn temporary uploads into documents of a submitted application."""
    for doc_type, upload in uploads.items():
        document = ApplicationDocument(
            application=application,
            doc_type=doc_type,
            stored_name=upload.stored_name,
            original_name=upload.original_name,
            content_type=upload.content_type,
            size_bytes=upload.size_bytes,
        )
        source = temp_path(upload)
        if not source.is_file():
            raise DomainError("An uploaded file is missing. Please upload it again.")
        source.replace(document_path(document))
        db.add(document)
        db.delete(upload)


def replace(db: Session, application: Application, uploads: dict[DocType, TempUpload]) -> None:
    """Put new files in place of the application's documents of the same kind."""
    for document in list(application.documents):
        if document.doc_type in uploads:
            document_path(document).unlink(missing_ok=True)
            application.documents.remove(document)
    db.flush()
    attach(db, application, uploads)
