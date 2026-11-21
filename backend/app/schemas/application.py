from datetime import date, time

from pydantic import BaseModel, ConfigDict, Field

from app.models import DocType, DrivingBand, Gender, Status, VehicleUsage


class _Form(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class MemberIn(_Form):
    name: str = Field(max_length=100)
    age: int
    gender: Gender


class ApplicationIn(_Form):
    """The whole six-step form, as one flat object.

    Only shapes and lengths are checked here. The rules of PRD Section 4 are
    applied in app.services.validation, which answers with a message per field.
    """

    # Step 1: group leader and journey
    leader_name: str = Field(max_length=100)
    leader_age: int
    leader_gender: Gender
    leader_mobile: str = Field(max_length=15)
    travel_date: date
    departure_time: time
    return_time: time
    origin_address: str = Field(max_length=500)
    origin_district_id: int
    origin_police_station_id: int

    # Step 2: destination
    destination_address: str = Field(max_length=500)
    destination_district_id: int
    destination_police_station_id: int | None = None
    driving_band: DrivingBand

    # Step 3: vehicle
    vehicle_reg_number: str = Field(max_length=20)
    vehicle_type_id: int
    vehicle_usage: VehicleUsage
    seating_capacity: int
    owner_name: str = Field(max_length=100)
    owner_mobile: str = Field(max_length=15)
    decl_not_goods_vehicle: bool = False
    decl_documents_valid: bool = False
    decl_no_unpaid_challans: bool = False

    # Step 4: driver and handyman
    driver_name: str = Field(max_length=100)
    licence_number: str = Field(max_length=25)
    licence_class: str = Field(max_length=60)
    licence_valid_until: date
    driver_mobile: str = Field(max_length=15)
    decl_licence_valid: bool = False
    decl_no_conviction: bool = False
    decl_driver_fit: bool = False
    has_handyman: bool = False
    handyman_name: str = Field(default="", max_length=100)
    handyman_mobile: str = Field(default="", max_length=15)

    # Step 5: passengers other than the group leader
    members: list[MemberIn] = Field(default_factory=list, max_length=150)

    # Step 6: emergency kit and undertaking
    kit_first_aid: bool = False
    kit_spare_tyre: bool = False
    kit_jack: bool = False
    kit_spanner: bool = False
    kit_fire_extinguisher: bool = False
    emergency_contacts_saved: bool = False
    undertaking_accepted: bool = False

    # Document type -> token of the temporary upload
    documents: dict[DocType, str] = Field(default_factory=dict)


class DuplicateInfo(BaseModel):
    vehicle: bool
    driver: bool
    message: str


class CheckResult(BaseModel):
    """The form is valid. `duplicate` is set when the duplicate check would block it."""

    total_people: int
    duplicate: DuplicateInfo | None = None


class OtpRequest(_Form):
    mobile: str = Field(max_length=15)
    captcha_id: str | None = Field(default=None, max_length=36)
    captcha_answer: str | None = Field(default=None, max_length=16)


class OtpSent(BaseModel):
    # Development only: the code itself, because no SMS is sent. Never set in production.
    dev_otp: str | None = None
    otp_id: str
    valid_minutes: int
    resend_after_seconds: int


class SubmitRequest(_Form):
    application: ApplicationIn
    otp_id: str = Field(max_length=36)
    otp_code: str = Field(max_length=8)
    # "This is my vehicle or driver: raise a claim" (PRD Section 10.1)
    raise_claim: bool = False


class Submitted(BaseModel):
    application_number: str
    status: Status
    message: str


class UploadOut(BaseModel):
    token: str
    doc_type: DocType
    original_name: str
    size_bytes: int


class VehicleTypeOut(BaseModel):
    id: int
    name: str
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class VehicleTypeCreate(_Form):
    name: str = Field(min_length=1, max_length=60)


class VehicleTypeUpdate(_Form):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    is_active: bool | None = None


class SeasonOut(BaseModel):
    start_date: date | None
    end_date: date | None

    model_config = ConfigDict(from_attributes=True)


class SeasonIn(BaseModel):
    start_date: date | None = None
    end_date: date | None = None


class DocumentRule(BaseModel):
    doc_type: DocType
    label: str
    required: bool
    note: str | None = None


class FormConfig(BaseModel):
    """Everything the public form needs to show the rules and repeat them."""

    today: date
    min_travel_date: date
    max_travel_date: date
    season: SeasonOut
    min_days_before_travel: int
    max_days_before_travel: int
    earliest_departure_hour: int
    latest_return_hour: int
    leader_min_age: int
    child_free_below_age: int
    upload_max_mb: int
    otp_length: int
    otp_resend_seconds: int
    vehicle_types: list[VehicleTypeOut]
    documents: list[DocumentRule]


# ------------------------------------------------------------ status page


class PublicStatus(BaseModel):
    """What anyone may see of an application: no personal details."""

    application_number: str
    travel_date: date
    status: Status
    status_label: str
    current_office: str
    remarks: str | None
    # What the office holding the application is doing with it. Empty once it is closed.
    working_status: str | None = None


class StatusOtpRequest(_Form):
    mobile: str | None = Field(default=None, max_length=15)
    application_number: str | None = Field(default=None, max_length=20)
    captcha_id: str | None = Field(default=None, max_length=36)
    captcha_answer: str | None = Field(default=None, max_length=16)


class StatusOtpSent(BaseModel):
    otp_id: str
    valid_minutes: int
    resend_after_seconds: int
    # The group leader's number with only the last two digits shown.
    sent_to: str | None = None
    dev_otp: str | None = None


class StatusSessionRequest(_Form):
    otp_id: str = Field(max_length=36)
    otp_code: str = Field(max_length=8)


class ApplicantMe(BaseModel):
    mobile: str
    expires_in_seconds: int


class DocumentOut(BaseModel):
    id: int
    doc_type: DocType
    label: str
    original_name: str
    size_bytes: int
    # Set by the DTO: checked against the original, or not yet checked (empty).
    verified: bool | None = None


class PassengerOut(BaseModel):
    position: int
    name: str
    age: int
    gender: Gender
    is_group_leader: bool

    model_config = ConfigDict(from_attributes=True)


class ApplicationDetail(PublicStatus):
    """The full application, for the group leader's own verified mobile."""

    submitted_on: date
    inspection_status: str
    can_correct: bool
    can_upload_inspection_certificate: bool
    # True while the application is approved: the permit and its QR code can be downloaded.
    can_download_permit: bool = False
    # The form values, in the shape the form itself uses, so a correction starts from them.
    form: dict[str, object]
    origin_district: str
    origin_police_station: str
    destination_district: str
    destination_police_station: str | None
    vehicle_type: str
    total_people: int
    passengers: list[PassengerOut]
    documents: list[DocumentOut]


class EmergencyContactOut(BaseModel):
    id: int
    district_id: int
    name: str
    phone: str
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class EmergencyContactCreate(_Form):
    district_id: int
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=3, max_length=40)


class EmergencyContactUpdate(_Form):
    district_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    phone: str | None = Field(default=None, min_length=3, max_length=40)
    is_active: bool | None = None
