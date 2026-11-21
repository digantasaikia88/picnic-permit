"""The work of the three offices: queue, application page and actions.

Every request is checked against the officer's role and jurisdiction here in
the backend. An application outside the jurisdiction answers "not found".
"""

import json

from fastapi import APIRouter, Depends, Form, Query, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.status import EXISTING, form_values
from app.core.database import get_db
from app.core.dependencies import require_roles
from app.core.errors import DomainError, NotFoundError
from app.core.timeutil import today_local
from app.models import (
    Application,
    ApplicationDocument,
    AuditLog,
    DocType,
    PoliceStation,
    Role,
    Status,
    User,
)
from app.schemas.application import DocumentOut, PassengerOut
from app.schemas.officer import (
    AcceptClaimRequest,
    AlertOut,
    ChoiceItem,
    ClaimOut,
    ClaimSide,
    ConfirmCertificateRequest,
    DtoFindingsRequest,
    EarlierCertificateOut,
    ForwardRequest,
    InspectionResultRequest,
    MobileFlag,
    NamedOption,
    OfficerCorrection,
    OfficerDetail,
    OfficerReference,
    PoliceRecordRequest,
    QueueItem,
    QueuePage,
    RejectClaimRequest,
    RemarkRequest,
    ScheduleInspectionRequest,
    TimelineEntry,
    TransferRequest,
    VerifyDocumentRequest,
    WorkingStatusRequest,
)
from app.services import (
    access,
    applications,
    claims,
    dto,
    flags,
    masters,
    officer,
    permit,
    police,
    uploads,
    validation,
    workflow,
)
from app.services import status as status_service
from app.services.access import Acting

router = APIRouter(prefix="/officer", tags=["officer"])

require_office = require_roles(*access.WORKFLOW_ROLES)
require_dto = require_roles(Role.DTO)

_FORWARD_LABELS = {
    Status.PENDING_DTO: "Forward to the police station",
    Status.PENDING_POLICE: "Forward to the DC office",
    Status.PENDING_DC: "Approve",
}

_TIMELINE_TITLES = {
    "application.submitted": "Submitted by the applicant",
    "application.submitted_as_claim": "Submitted as a duplicate claim",
    "application.forwarded": "Forwarded",
    "application.approved": "Approved",
    "application.returned": "Returned to the applicant",
    "application.resubmitted": "Resubmitted by the applicant",
    "application.rejected": "Rejected",
    "application.sent_back_to_dto": "Sent back to the DTO",
    "application.corrected_by_applicant": "Corrected by the applicant",
    "application.corrected_by_officer": "Corrected by the office",
    "application.working_status": "Working status changed",
    "application.inspection_certificate_uploaded": "Inspection certificate uploaded",
    "application.inspection_certificate_uploaded_by_office": (
        "Inspection certificate uploaded by the office"
    ),
    "application.dto_findings": "VAHAN, challan and SARATHI findings recorded",
    "application.document_verified": "Document checked against the original",
    "application.inspection_scheduled": "Inspection scheduled",
    "application.inspection_recorded": "Inspection result recorded",
    "application.certificate_confirmed": "Inspection certificate confirmed",
    "application.police_record": "Police verification recorded",
    "application.transferred": "Transferred to another police station",
    "application.claim_accepted": "Duplicate claim accepted",
    "application.expired": "Expired: the travel date is over",
}


def _item(application: Application, user: User, flagged: set[str] | None = None) -> QueueItem:
    a = application
    return QueueItem(
        id=a.id,
        application_number=a.application_number,
        travel_date=a.travel_date,
        days_left=(a.travel_date - today_local()).days,
        status=a.status,
        status_label=workflow.STATUS_LABELS[a.status],
        working_status=officer.working_status_label(a),
        current_office=status_service.current_office(a),
        leader_name=a.leader_name,
        leader_mobile=a.leader_mobile,
        vehicle_reg_number=a.vehicle_reg_number,
        origin_police_station=a.origin_police_station.name,
        destination=a.destination_address,
        total_people=a.total_people,
        needs_dc_specific_approval=a.needs_dc_specific_approval,
        inspection_status=a.inspection_status.value,
        is_duplicate_claim=a.is_duplicate_claim,
        mobile_flagged=a.leader_mobile in (flagged or ()),
        with_my_office=access.holds(user, a),
    )


def _items(db: Session, rows: list[Application], user: User) -> list[QueueItem]:
    flagged = flags.flagged_among(db, {a.leader_mobile for a in rows})
    return [_item(a, user, flagged) for a in rows]


def _documents(application: Application) -> list[DocumentOut]:
    return [
        DocumentOut(
            id=d.id,
            doc_type=d.doc_type,
            label=validation.DOCUMENT_LABELS.get(d.doc_type, "Road tax payment proof"),
            original_name=d.original_name,
            size_bytes=d.size_bytes,
            verified=d.verified,
        )
        for d in sorted(application.documents, key=lambda d: d.id)
    ]


def _file(document: ApplicationDocument) -> FileResponse:
    path = uploads.document_path(document)
    if not path.is_file():
        raise NotFoundError("The file is missing.")
    number = document.application.application_number
    return FileResponse(
        path,
        media_type=document.content_type,
        filename=f"{number}_{document.doc_type.value}{path.suffix}",
        content_disposition_type="inline",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


def _entry(row: AuditLog) -> TimelineEntry:
    new = row.new_value or {}
    return TimelineEntry(
        at=row.at,
        action=row.action,
        title=_TIMELINE_TITLES.get(row.action, row.action),
        by=row.actor_label,
        officer_name=row.officer_name,
        officer_designation=row.officer_designation,
        remarks=new.get("remarks"),
        old_value=row.old_value,
        new_value=row.new_value,
    )


def _detail(db: Session, application: Application, user: User) -> OfficerDetail:
    a = application
    flag = flags.get(db, a.leader_mobile)
    holds = access.holds(user, a)
    permit_state = permit.state(a, today=today_local())
    return OfficerDetail(
        **_item(a, user, {a.leader_mobile} if flag else None).model_dump(),
        forward_blockers=workflow.forward_blockers(db, a) if holds else [],
        mobile_flag=(
            MobileFlag(
                reason=flag.reason,
                application_number=flag.application_number,
                is_blocked=flag.is_blocked,
            )
            if flag
            else None
        ),
        dto_findings=a.dto_findings,
        challan_warning=dto.challan_warning(a),
        inspection=a.inspection,
        inspection_label=dto.INSPECTION_LABELS[a.inspection_status],
        certificate_confirmed=workflow.certificate_confirmed(db, a),
        confirmed_certificate_id=a.certificate_confirmed_doc_id,
        earlier_certificates=[
            EarlierCertificateOut(
                document_id=item.document.id,
                application_number=item.application.application_number,
                travel_date=item.application.travel_date,
                uploaded_at=item.document.uploaded_at,
                original_name=item.document.original_name,
                confirmed=item.confirmed,
            )
            for item in dto.earlier_certificates(db, a)
        ],
        police_findings=a.police_findings,
        dc_specific_approval_remark=a.dc_specific_approval_remark,
        permit_state=permit_state.value if permit_state else None,
        permit_state_label=permit.STATE_LABELS[permit_state] if permit_state else None,
        approved_by=a.approved_by,
        can_print_permit=a.status == Status.APPROVED and a.verify_code is not None,
        submitted_on=a.submission_date,
        remarks=a.status_remarks,
        forward_label=_FORWARD_LABELS.get(a.status) if access.holds(user, a) else None,
        form=form_values(a),
        origin_district=a.origin_district.name,
        destination_district=a.destination_district.name,
        destination_police_station=(
            a.destination_police_station.name if a.destination_police_station else None
        ),
        vehicle_type=a.vehicle_type.name,
        passengers=[PassengerOut.model_validate(p) for p in a.passengers],
        documents=_documents(a),
        alerts=[
            AlertOut(
                application_number=alert.application_number,
                travel_date=alert.travel_date,
                status=alert.status,
                status_label=workflow.STATUS_LABELS[alert.status],
                district=alert.district,
                same_vehicle=alert.same_vehicle,
                same_driver=alert.same_driver,
                same_leader=alert.same_leader,
                rejection_reason=alert.rejection_reason,
            )
            for alert in officer.alerts(db, a)
        ],
        timeline=[_entry(row) for row in officer.timeline(db, a)],
    )


def _acting(user: User, body) -> Acting:
    return Acting(user=user, name=body.officer_name, designation=body.officer_designation)


def _answer(db: Session, application: Application, user: User) -> OfficerDetail:
    db.commit()
    db.refresh(application)
    # After the action the application may have left this office's view
    # (for example, moved to another district). The answer is still given once.
    return _detail(db, application, user)


# ------------------------------------------------------------------- lists


@router.get("/reference", response_model=OfficerReference, summary="Lists for the action forms")
def reference(
    db: Session = Depends(get_db), user: User = Depends(require_office)
) -> OfficerReference:
    district = user.jurisdiction_district

    def choices(items: dict[str, str]) -> list[ChoiceItem]:
        return [ChoiceItem(key=key, label=label) for key, label in items.items()]

    return OfficerReference(
        vahan_items=choices(dto.VAHAN_ITEMS),
        sarathi_items=choices(dto.SARATHI_ITEMS),
        checklist_items=choices(dto.CHECKLIST),
        police_stations=(
            [
                NamedOption.model_validate(station)
                for station in masters.list_police_stations(db, district_id=district.id)
                if station.is_active
            ]
            if district
            else []
        ),
        duplicate_claims=len(claims.waiting(db, user)) if user.role == Role.DTO else 0,
        # Each office is offered only the working statuses meant for it.
        working_statuses=[
            NamedOption.model_validate(w) for w in officer.working_statuses(db, role=user.role)
        ],
        return_reasons=[NamedOption.model_validate(r) for r in officer.reasons(db, "RETURN")],
        reject_reasons=[NamedOption.model_validate(r) for r in officer.reasons(db, "REJECT")],
    )


@router.get("/queue", response_model=list[QueueItem], summary="Applications waiting for my office")
def my_queue(
    search: str | None = Query(default=None, max_length=40),
    db: Session = Depends(get_db),
    user: User = Depends(require_office),
) -> list[QueueItem]:
    return _items(db, officer.queue(db, user, search=search), user)


@router.get(
    "/applications",
    response_model=QueuePage,
    summary="Every application in my jurisdiction, to look at",
)
def all_applications(
    status_filter: Status | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None, max_length=40),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_office),
) -> QueuePage:
    rows, total = officer.visible(
        db, user, status=status_filter, search=search, page=page, page_size=page_size
    )
    return QueuePage(items=_items(db, rows, user), total=total, page=page, page_size=page_size)


@router.get("/applications/{application_id}", response_model=OfficerDetail)
def application_detail(
    application_id: int,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_office),
) -> OfficerDetail:
    response.headers["Cache-Control"] = "no-store"
    return _detail(db, officer.get_for(db, user, application_id), user)


@router.get("/applications/{application_id}/documents/{document_id}", summary="Open one document")
def document(
    application_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_office),
) -> FileResponse:
    application = officer.get_for(db, user, application_id)
    return _file(status_service.own_document(application, document_id))


# ----------------------------------------------------------------- actions


@router.post(
    "/applications/{application_id}/forward",
    response_model=OfficerDetail,
    summary="Forward to the next office; for the DC office, approve",
)
def forward(
    application_id: int,
    body: ForwardRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_office),
) -> OfficerDetail:
    application = officer.get_for(db, user, application_id)
    workflow.forward(
        db,
        application,
        acting=_acting(user, body),
        remarks=body.remarks,
        specific_approval_remark=body.specific_approval_remark,
    )
    return _answer(db, application, user)


@router.post(
    "/applications/{application_id}/return",
    response_model=OfficerDetail,
    summary="Return to the applicant for correction",
)
def return_to_applicant(
    application_id: int,
    body: RemarkRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_office),
) -> OfficerDetail:
    application = officer.get_for(db, user, application_id)
    remarks = officer.compose_remarks(db, "RETURN", body.reason_id, body.remarks)
    workflow.return_to_applicant(db, application, acting=_acting(user, body), remarks=remarks)
    return _answer(db, application, user)


@router.post(
    "/applications/{application_id}/reject",
    response_model=OfficerDetail,
    summary="Reject with a reason",
)
def reject(
    application_id: int,
    body: RemarkRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_office),
) -> OfficerDetail:
    application = officer.get_for(db, user, application_id)
    reason = officer.compose_remarks(db, "REJECT", body.reason_id, body.remarks)
    acting = _acting(user, body)
    workflow.reject(db, application, acting=acting, reason=reason)
    # Section 10.1: the DTO may flag the number behind a fake or prank application.
    if body.flag_mobile and user.role == Role.DTO:
        flags.flag(db, application, acting=acting, reason=reason)
    return _answer(db, application, user)


@router.post(
    "/applications/{application_id}/working-status",
    response_model=OfficerDetail,
    summary="Say what the office is doing with the application",
)
def set_working_status(
    application_id: int,
    body: WorkingStatusRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_office),
) -> OfficerDetail:
    application = officer.get_for(db, user, application_id)
    officer.set_working_status(
        db, application, acting=_acting(user, body), working_status_id=body.working_status_id
    )
    return _answer(db, application, user)


@router.put(
    "/applications/{application_id}",
    response_model=OfficerDetail,
    summary="Correct the data or documents of an application the office holds",
)
def correct(
    application_id: int,
    body: OfficerCorrection,
    db: Session = Depends(get_db),
    user: User = Depends(require_office),
) -> OfficerDetail:
    application = officer.get_for(db, user, application_id)
    # Documents already on the application come back as "existing:<id>"; only new files count.
    body.application.documents = {
        doc_type: token
        for doc_type, token in body.application.documents.items()
        if not token.startswith(EXISTING)
    }
    applications.correct_by_officer(db, application, body.application, acting=_acting(user, body))
    return _answer(db, application, user)


# ------------------------------------------------------- the DTO's own work


@router.post(
    "/applications/{application_id}/dto-findings",
    response_model=OfficerDetail,
    summary="DTO: record the VAHAN, challan and SARATHI findings",
)
def record_dto_findings(
    application_id: int,
    body: DtoFindingsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_office),
) -> OfficerDetail:
    application = officer.get_for(db, user, application_id)
    dto.record_findings(
        db,
        application,
        acting=_acting(user, body),
        vahan=body.vahan,
        vahan_remarks=body.vahan_remarks,
        challans_unpaid=body.challans_unpaid,
        challans_on_record=body.challans_on_record,
        challan_remarks=body.challan_remarks,
        sarathi=body.sarathi,
        sarathi_remarks=body.sarathi_remarks,
    )
    return _answer(db, application, user)


@router.post(
    "/applications/{application_id}/documents/{document_id}/verify",
    response_model=OfficerDetail,
    summary="DTO: mark a document as checked against the original",
)
def verify_document(
    application_id: int,
    document_id: int,
    body: VerifyDocumentRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_office),
) -> OfficerDetail:
    application = officer.get_for(db, user, application_id)
    dto.verify_document(
        db,
        application,
        acting=_acting(user, body),
        document_id=document_id,
        verified=body.verified,
    )
    return _answer(db, application, user)


@router.post(
    "/applications/{application_id}/inspection/schedule",
    response_model=OfficerDetail,
    summary="DTO: fix the date, time and place of the vehicle inspection",
)
def schedule_inspection(
    application_id: int,
    body: ScheduleInspectionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_office),
) -> OfficerDetail:
    application = officer.get_for(db, user, application_id)
    dto.schedule_inspection(
        db, application, acting=_acting(user, body), on=body.on, at=body.at, place=body.place
    )
    return _answer(db, application, user)


@router.post(
    "/applications/{application_id}/inspection/result",
    response_model=OfficerDetail,
    summary="DTO: record the inspection checklist and result",
)
def record_inspection(
    application_id: int,
    body: InspectionResultRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_office),
) -> OfficerDetail:
    application = officer.get_for(db, user, application_id)
    dto.record_inspection(
        db,
        application,
        acting=_acting(user, body),
        checklist=body.checklist,
        inspected_on=body.inspected_on,
        inspecting_officer=body.inspecting_officer,
        passed=body.passed,
        remarks=body.remarks,
    )
    return _answer(db, application, user)


@router.post(
    "/applications/{application_id}/inspection/confirm-certificate",
    response_model=OfficerDetail,
    summary="DTO: confirm an inspection certificate, or take the confirmation back",
)
def confirm_certificate(
    application_id: int,
    body: ConfirmCertificateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_office),
) -> OfficerDetail:
    application = officer.get_for(db, user, application_id)
    dto.confirm_certificate(
        db, application, acting=_acting(user, body), document_id=body.document_id
    )
    return _answer(db, application, user)


@router.post(
    "/applications/{application_id}/inspection/result-with-certificate",
    response_model=OfficerDetail,
    summary="DTO: record the inspection result and upload the certificate issued",
)
async def record_inspection_with_certificate(
    application_id: int,
    file: UploadFile,
    data: str = Form(max_length=5000),
    officer_name: str = Form(default="", max_length=100),
    officer_designation: str = Form(default="", max_length=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_office),
) -> OfficerDetail:
    """The same as the inspection result, sent as a form so that it can carry the file.

    `data` is the inspection result as JSON. The scanned certificate takes the
    place of any certificate already on the application.
    """
    try:
        fields = json.loads(data)
        # The name and designation may come as fields of the form, as in the other dialogs.
        if officer_name:
            fields["officer_name"] = officer_name
        if officer_designation:
            fields["officer_designation"] = officer_designation
        body = InspectionResultRequest.model_validate(fields)
    except (ValueError, TypeError, ValidationError) as error:
        raise DomainError("Fill every field of the inspection result.") from error
    application = officer.get_for(db, user, application_id)
    acting = _acting(user, body)
    # Checked before the file is read, so that only the DTO that holds it can store a file.
    access.require_holds(user, application)
    if not body.passed:
        raise DomainError("A certificate is uploaded only for a vehicle that passed inspection.")
    content = await file.read(uploads.max_bytes(db) + 1)
    if content:
        # Refuse a wrong kind of file before anything is recorded or any SMS goes out.
        uploads.sniff(content)
    # The result first: if a rule fails, no file is stored.
    dto.record_inspection(
        db,
        application,
        acting=acting,
        checklist=body.checklist,
        inspected_on=body.inspected_on,
        inspecting_officer=body.inspecting_officer,
        passed=body.passed,
        remarks=body.remarks,
    )
    upload = uploads.save_temp(
        db,
        filename=file.filename or "",
        content=content,
        doc_type=DocType.INSPECTION_CERTIFICATE,
    )
    dto.upload_certificate(db, application, acting=acting, upload=upload, notify=False)
    return _answer(db, application, user)


@router.get(
    "/applications/{application_id}/certificates/{document_id}",
    summary="Open an inspection certificate on record for the same vehicle",
)
def earlier_certificate(
    application_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_office),
) -> FileResponse:
    application = officer.get_for(db, user, application_id)
    return _file(dto.certificate_for(db, application, document_id))


# -------------------------------------------- the police station's own work


@router.post(
    "/applications/{application_id}/police-record",
    response_model=OfficerDetail,
    summary="Police station: destination police station, driving time, remarks, checkpoints",
)
def record_police(
    application_id: int,
    body: PoliceRecordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_office),
) -> OfficerDetail:
    application = officer.get_for(db, user, application_id)
    police.record(
        db,
        application,
        acting=_acting(user, body),
        destination_police_station_id=body.destination_police_station_id,
        driving_band=body.driving_band,
        verification_remarks=body.verification_remarks,
        checkpoints=body.checkpoints,
        comments=body.comments,
    )
    return _answer(db, application, user)


@router.post(
    "/applications/{application_id}/transfer",
    response_model=OfficerDetail,
    summary="Police station: transfer to another police station of the same district",
)
def transfer(
    application_id: int,
    body: TransferRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_office),
) -> OfficerDetail:
    application = officer.get_for(db, user, application_id)
    station = db.get(PoliceStation, body.police_station_id)
    if station is None:
        raise NotFoundError("Police station not found.")
    workflow.transfer(
        db, application, acting=_acting(user, body), station=station, remarks=body.remarks
    )
    return _answer(db, application, user)


# -------------------------------------------------------- duplicate claims


def _side(
    db: Session, application: Application, *, same_vehicle: bool, same_driver: bool
) -> ClaimSide:
    a = application
    return ClaimSide(
        id=a.id,
        application_number=a.application_number,
        status=a.status,
        status_label=workflow.STATUS_LABELS[a.status],
        current_office=status_service.current_office(a),
        district=a.origin_district.name,
        submitted_at=a.submitted_at,
        travel_date=a.travel_date,
        leader_name=a.leader_name,
        leader_mobile=a.leader_mobile,
        mobile_flagged=flags.get(db, a.leader_mobile) is not None,
        owner_name=a.owner_name,
        owner_mobile=a.owner_mobile,
        vehicle_reg_number=a.vehicle_reg_number,
        driver_name=a.driver_name,
        licence_number=a.licence_number,
        driver_mobile=a.driver_mobile,
        same_vehicle=same_vehicle,
        same_driver=same_driver,
        documents=_documents(a),
    )


def _claim(db: Session, claim: Application) -> ClaimOut:
    return ClaimOut(
        # "Same vehicle" and "same driver" are said of the applications that block the claim.
        claim=_side(db, claim, same_vehicle=False, same_driver=False),
        blocking=[
            _side(
                db, item.application, same_vehicle=item.same_vehicle, same_driver=item.same_driver
            )
            for item in claims.blocking(db, claim)
        ],
    )


@router.get(
    "/claims", response_model=list[ClaimOut], summary="DTO: duplicate claims waiting for my office"
)
def list_claims(db: Session = Depends(get_db), user: User = Depends(require_dto)) -> list[ClaimOut]:
    return [_claim(db, claim) for claim in claims.waiting(db, user)]


@router.get("/claims/{application_id}", response_model=ClaimOut, summary="DTO: one duplicate claim")
def claim_detail(
    application_id: int,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_dto),
) -> ClaimOut:
    response.headers["Cache-Control"] = "no-store"
    return _claim(db, claims.get(db, user, application_id))


@router.get(
    "/claims/{application_id}/documents/{document_id}",
    summary="DTO: open a document of the claim",
)
def claim_document(
    application_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_dto),
) -> FileResponse:
    claim = claims.get(db, user, application_id)
    return _file(status_service.own_document(claim, document_id))


@router.get(
    "/claims/{application_id}/others/{other_id}/documents/{document_id}",
    summary="DTO: open a document of the application that blocks the claim",
)
def claim_other_document(
    application_id: int,
    other_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_dto),
) -> FileResponse:
    claim = claims.get(db, user, application_id)
    return _file(claims.other_document(db, claim, other_id, document_id))


@router.post(
    "/claims/{application_id}/accept",
    response_model=OfficerDetail,
    summary="DTO: the claim is genuine; reject what blocks it and take the claim up",
)
def accept_claim(
    application_id: int,
    body: AcceptClaimRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_dto),
) -> OfficerDetail:
    claim = claims.get(db, user, application_id)
    claims.accept(
        db,
        claim,
        acting=_acting(user, body),
        remarks=body.remarks,
        flag_mobiles=body.flag_mobiles,
    )
    return _answer(db, claim, user)


@router.post(
    "/claims/{application_id}/reject",
    response_model=OfficerDetail,
    summary="DTO: the claim is not genuine; close it",
)
def reject_claim(
    application_id: int,
    body: RejectClaimRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_dto),
) -> OfficerDetail:
    claim = claims.get(db, user, application_id)
    reason = officer.compose_remarks(db, "REJECT", body.reason_id, body.remarks)
    claims.reject(
        db, claim, acting=_acting(user, body), reason=reason, flag_mobile=body.flag_mobile
    )
    return _answer(db, claim, user)


# ---------------------------------------------------------------- printing


def _pdf(content: bytes, filename: str) -> Response:
    return Response(
        content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/applications/{application_id}/permit.pdf", summary="The permit, as the applicant gets it"
)
def permit_pdf(
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_office),
) -> Response:
    application = officer.get_for(db, user, application_id)
    return _pdf(permit.permit_pdf(application), f"permit_{application.application_number}.pdf")


@router.get("/applications/{application_id}/permit-qr.pdf", summary="Only the QR code, large")
def permit_qr_pdf(
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_office),
) -> Response:
    application = officer.get_for(db, user, application_id)
    return _pdf(permit.large_qr_pdf(application), f"permit_qr_{application.application_number}.pdf")


@router.get("/applications/{application_id}/application.pdf", summary="The application, to print")
def application_pdf(
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_office),
) -> Response:
    application = officer.get_for(db, user, application_id)
    content = permit.application_pdf(
        application,
        status_label=workflow.STATUS_LABELS[application.status],
        office=status_service.current_office(application),
    )
    return _pdf(content, f"application_{application.application_number}.pdf")
