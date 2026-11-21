from datetime import date, datetime, time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import DrivingBand, Status
from app.schemas.application import ApplicationIn, DocumentOut, PassengerOut


class _Action(BaseModel):
    """Every action names the officer who takes it: an office may share one user ID."""

    model_config = ConfigDict(str_strip_whitespace=True)

    officer_name: str = Field(min_length=1, max_length=100)
    officer_designation: str = Field(min_length=1, max_length=100)


class ForwardRequest(_Action):
    remarks: str = Field(default="", max_length=1000)
    # The DC office, approving a 60 to 90 minute journey: mandatory.
    specific_approval_remark: str = Field(default="", max_length=1000)


class RemarkRequest(_Action):
    """Return to the applicant, or reject: a reason from the list, a remark, or both."""

    reason_id: int | None = None
    remarks: str = Field(default="", max_length=1000)
    # The DTO, rejecting a fake or prank application: flag the mobile number that filed it.
    flag_mobile: bool = False


class WorkingStatusRequest(_Action):
    # Empty means "Received".
    working_status_id: int | None = None


class OfficerCorrection(_Action):
    application: ApplicationIn


class QueueItem(BaseModel):
    id: int
    application_number: str
    travel_date: date
    days_left: int
    status: Status
    status_label: str
    working_status: str | None
    current_office: str
    leader_name: str
    leader_mobile: str
    vehicle_reg_number: str
    origin_police_station: str
    destination: str
    total_people: int
    needs_dc_specific_approval: bool
    inspection_status: str
    is_duplicate_claim: bool
    # The group leader's mobile number was flagged for a fake or prank application.
    mobile_flagged: bool = False
    # True when this office can act on it now.
    with_my_office: bool


class QueuePage(BaseModel):
    items: list[QueueItem]
    total: int
    page: int
    page_size: int


class AlertOut(BaseModel):
    application_number: str
    travel_date: date
    status: Status
    status_label: str
    district: str
    same_vehicle: bool
    same_driver: bool
    same_leader: bool
    rejection_reason: str | None


class TimelineEntry(BaseModel):
    at: datetime
    action: str
    title: str
    by: str
    officer_name: str | None
    officer_designation: str | None
    remarks: str | None
    old_value: dict[str, Any] | None
    new_value: dict[str, Any] | None


class OfficerDetail(QueueItem):
    submitted_on: date
    remarks: str | None
    # What "forward" does at this stage, as the button label. Empty if the office cannot act.
    forward_label: str | None
    form: dict[str, object]
    origin_district: str
    destination_district: str
    destination_police_station: str | None
    vehicle_type: str
    passengers: list[PassengerOut]
    documents: list[DocumentOut]
    alerts: list[AlertOut]
    timeline: list[TimelineEntry]
    # What still stops the office from forwarding. Empty when it can forward.
    forward_blockers: list[str] = []
    mobile_flag: MobileFlag | None = None
    # Section 7.1
    dto_findings: dict[str, Any] | None = None
    challan_warning: bool = False
    inspection: dict[str, Any] | None = None
    inspection_label: str = ""
    certificate_confirmed: bool = False
    confirmed_certificate_id: int | None = None
    earlier_certificates: list[EarlierCertificateOut] = []
    # Section 7.2
    police_findings: dict[str, Any] | None = None
    # Section 7.3
    dc_specific_approval_remark: str | None = None
    # Section 8: Valid, Cancelled or Expired once a permit was issued; empty before.
    permit_state: str | None = None
    permit_state_label: str | None = None
    approved_by: str | None = None
    # True while the permit can be printed (the application is approved).
    can_print_permit: bool = False


class NamedOption(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class OfficerReference(BaseModel):
    working_statuses: list[NamedOption]
    return_reasons: list[NamedOption]
    reject_reasons: list[NamedOption]
    # The items of the DTO's checks and of the inspection checklist, in order.
    vahan_items: list[ChoiceItem] = []
    sarathi_items: list[ChoiceItem] = []
    checklist_items: list[ChoiceItem] = []
    # Police stations of the user's own district, for a transfer.
    police_stations: list[NamedOption] = []
    duplicate_claims: int = 0


class WorkingStatusOut(NamedOption):
    is_active: bool = True
    for_dto: bool = True
    for_police: bool = True
    for_dc: bool = True


class WorkingStatusCreate(BaseModel):
    """A working status and the offices it is offered to."""

    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=160)
    for_dto: bool = True
    for_police: bool = True
    for_dc: bool = True


class WorkingStatusUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    is_active: bool | None = None
    for_dto: bool | None = None
    for_police: bool | None = None
    for_dc: bool | None = None


class NameCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=160)


class NameUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    is_active: bool | None = None


class ReasonOut(NamedOption):
    kind: str
    is_active: bool = True


class ReasonCreate(NameCreate):
    kind: str = Field(pattern="^(RETURN|REJECT)$")


# ------------------------------------------------------------- part B: DTO


class DtoFindingsRequest(_Action):
    """What the DTO found in VAHAN, in the challan records and in SARATHI."""

    vahan: dict[str, str] = Field(default_factory=dict)
    vahan_remarks: str = Field(default="", max_length=1000)
    challans_unpaid: int | None = Field(default=None, ge=0, le=999)
    challans_on_record: int | None = Field(default=None, ge=0, le=999)
    challan_remarks: str = Field(default="", max_length=1000)
    sarathi: dict[str, str] = Field(default_factory=dict)
    sarathi_remarks: str = Field(default="", max_length=1000)


class VerifyDocumentRequest(_Action):
    # True: verified against the original. False: not verified. Empty: not yet checked.
    verified: bool | None = None


class ScheduleInspectionRequest(_Action):
    on: date
    at: time
    place: str = Field(min_length=1, max_length=200)


class InspectionResultRequest(_Action):
    checklist: dict[str, str]
    inspected_on: date
    inspecting_officer: str = Field(min_length=1, max_length=100)
    passed: bool
    remarks: str = Field(default="", max_length=1000)


class ConfirmCertificateRequest(_Action):
    # Empty takes the confirmation back.
    document_id: int | None = None


class EarlierCertificateOut(BaseModel):
    document_id: int
    application_number: str
    travel_date: date
    uploaded_at: datetime
    original_name: str
    confirmed: bool


class ChoiceItem(BaseModel):
    key: str
    label: str


# ---------------------------------------------------------- part B: police


class PoliceRecordRequest(_Action):
    destination_police_station_id: int
    driving_band: DrivingBand
    verification_remarks: str = Field(default="", max_length=1000)
    checkpoints: str = Field(default="", max_length=1000)
    comments: str = Field(default="", max_length=1000)


class TransferRequest(_Action):
    police_station_id: int
    remarks: str = Field(min_length=1, max_length=1000)


# ------------------------------------------------- part B: duplicate claims


class ClaimSide(BaseModel):
    """One of the two applications the DTO compares."""

    id: int
    application_number: str
    status: Status
    status_label: str
    current_office: str
    district: str
    submitted_at: datetime
    travel_date: date
    leader_name: str
    leader_mobile: str
    mobile_flagged: bool
    owner_name: str
    owner_mobile: str
    vehicle_reg_number: str
    driver_name: str
    licence_number: str
    driver_mobile: str
    same_vehicle: bool
    same_driver: bool
    documents: list[DocumentOut]


class ClaimOut(BaseModel):
    claim: ClaimSide
    blocking: list[ClaimSide]


class AcceptClaimRequest(_Action):
    remarks: str = Field(default="", max_length=1000)
    flag_mobiles: bool = False


class RejectClaimRequest(RemarkRequest):
    pass


# ---------------------------------------------------- part B: flagged mobiles


class MobileFlag(BaseModel):
    reason: str
    application_number: str | None
    is_blocked: bool


class FlaggedMobileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mobile: str
    reason: str
    application_number: str | None
    flagged_by: str
    is_blocked: bool
    created_at: datetime


class FlaggedMobileUpdate(BaseModel):
    is_blocked: bool


OfficerDetail.model_rebuild()
OfficerReference.model_rebuild()
