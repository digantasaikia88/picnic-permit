"""The permit (PRD Section 8): its live state, and the documents to print.

A permit exists once the DC office has approved the application. Its number is
the application number. The PDFs are made afresh on every download from the
data of the application, so they are never out of step with it.
"""

from datetime import date, time
from enum import StrEnum
from functools import cache
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from weasyprint import HTML

from app.core.config import get_settings
from app.core.errors import DomainError
from app.models import Application, Status
from app.services import dto, police, qr, validation

_ASSETS = Path(__file__).resolve().parent.parent / "assets"

# The side of the code itself (white margin not counted), in centimetres.
PERMIT_QR_CM = 10.0  # the SOP: no less than 10 cm x 10 cm
LARGE_QR_CM = 16.0  # the separate windscreen sheet: about 18 cm with its margin


class PermitState(StrEnum):
    VALID = "VALID"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


STATE_LABELS = {
    PermitState.VALID: "Valid",
    PermitState.CANCELLED: "Cancelled",
    PermitState.EXPIRED: "Expired",
}


def state(application: Application, *, today: date) -> PermitState | None:
    """Valid, Cancelled or Expired; None when no permit was ever issued.

    The date decides expiry by itself, so the answer is right even before the
    expiry job has run.
    """
    if application.verify_code is None:
        return None
    if application.status == Status.CANCELLED:
        return PermitState.CANCELLED
    if application.status == Status.EXPIRED:
        return PermitState.EXPIRED
    if application.status == Status.APPROVED:
        return PermitState.EXPIRED if application.travel_date < today else PermitState.VALID
    return None


def require_permit(application: Application) -> None:
    """A permit can be printed while the application is approved (PRD Section 8)."""
    if application.status != Status.APPROVED or application.verify_code is None:
        raise DomainError("A permit can be downloaded only for an approved application.")


# ------------------------------------------------------------------ pieces


def _e(value: object) -> str:
    return escape(str(value if value is not None else ""))


def _clock(value: time) -> str:
    return value.strftime("%I:%M %p").lstrip("0")


def _day(value: date) -> str:
    return f"{value.day} {value:%B %Y}"


@cache
def _emblem_uri() -> str:
    return (_ASSETS / "emblem_assam.svg").as_uri()


def _approved_on(application: Application) -> str:
    if application.approved_at is None:
        return ""
    local = application.approved_at.astimezone(ZoneInfo(get_settings().app_timezone))
    return _day(local.date())


_BASE_CSS = """
@page { size: A4; margin: 1.2cm 1.4cm; }
* { box-sizing: border-box; }
body { font-family: "DejaVu Sans", sans-serif; font-size: 9.5pt; color: #111; margin: 0; }
h1 { font-size: 14pt; margin: 0; }
h2 { font-size: 10.5pt; margin: 10pt 0 3pt; border-bottom: 0.6pt solid #999; padding-bottom: 2pt; }
.head { display: flex; align-items: center; gap: 12pt; border-bottom: 1.2pt solid #111;
        padding-bottom: 6pt; }
.head img { height: 1.9cm; }
.head .gov { font-size: 10pt; }
.head .number { margin-left: auto; text-align: right; font-size: 9pt; }
.head .number b { display: block; font-size: 15pt; letter-spacing: 0.5pt; }
table { width: 100%; border-collapse: collapse; }
td, th { padding: 2.2pt 4pt 2.2pt 0; vertical-align: top; text-align: left; }
td.k { width: 26%; color: #444; }
.small { font-size: 8pt; color: #333; }
ul { margin: 2pt 0 0; padding-left: 13pt; }
li { margin-bottom: 1.5pt; }
"""


def _head(application: Application, title: str) -> str:
    return f"""
<div class="head">
  <img src="{_emblem_uri()}" alt="">
  <div>
    <div class="gov">Government of Assam · Transport Department</div>
    <h1>{_e(title)}</h1>
  </div>
  <div class="number">Permit number<b>{_e(application.application_number)}</b></div>
</div>"""


def _rows(pairs: list[tuple[str, object]]) -> str:
    return "".join(f'<tr><td class="k">{_e(k)}</td><td>{_e(v)}</td></tr>' for k, v in pairs)


def _pdf(body: str, css: str = "") -> bytes:
    html = (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<style>{_BASE_CSS}{css}</style></head><body>{body}</body></html>"
    )
    return HTML(string=html, base_url=str(_ASSETS)).write_pdf()


def _journey_rows(application: Application) -> list[tuple[str, object]]:
    a = application
    return [
        ("Date of travel", _day(a.travel_date)),
        ("Permitted hours", f"{_clock(a.departure_time)} to {_clock(a.return_time)}"),
        ("Vehicle", f"{a.vehicle_reg_number} ({a.vehicle_type.name})"),
        ("Driver", f"{a.driver_name}, licence {a.licence_number}"),
        ("People travelling", f"{a.total_people} (group, driver and handyman)"),
        (
            "Starting point",
            f"{a.origin_address} ({a.origin_police_station.name}, {a.origin_district.name})",
        ),
        ("Destination", f"{a.destination_address} ({a.destination_district.name})"),
        ("Group leader", f"{a.leader_name}, {a.leader_mobile}"),
    ]


# ------------------------------------------------------------------ permit


def permit_pdf(application: Application) -> bytes:
    """The permit: one A4 page, with the QR code at 10 cm to cut out and paste."""
    require_permit(application)
    a = application
    code = qr.make(a)
    side = qr.printed_size_cm(code, squares_cm=PERMIT_QR_CM)
    approved = f"Approved by {a.approved_by}, " if a.approved_by else "Approved by the "
    css = f"""
.cut {{ margin: 8pt auto 2pt; width: {side + 0.5:.2f}cm; border: 0.8pt dashed #555;
        padding: 0.2cm; text-align: center; }}
.cut img {{ width: {side:.2f}cm; height: {side:.2f}cm; display: block; margin: 0 auto; }}
.cut .cap {{ font-size: 9pt; font-weight: bold; }}
.note {{ text-align: center; font-size: 8.5pt; margin-bottom: 4pt; }}
"""
    body = f"""
{_head(a, "Picnic/Recreational Journey Permit")}
<div class="cut">
  <img src="{qr.svg_data_uri(code)}" alt="QR code of the permit">
  <div class="cap">{_e(a.application_number)} · {_e(a.vehicle_reg_number)} ·
    {_e(f"{a.travel_date:%d-%m-%Y}")}</div>
</div>
<p class="note">Cut along the dashed line and paste the QR code inside the driver's-side
windscreen, facing out. It must stay there for the whole journey.</p>
<h2>This permit is valid only for</h2>
<table>{_rows(_journey_rows(a))}</table>
<h2>Conditions</h2>
<ul class="small">
  <li>Valid only for the vehicle, driver, date, hours and destination shown above. It expires
      at the end of the date of travel.</li>
  <li>Only the people listed in the application may travel. No extra stop and no change of
      destination.</li>
  <li>The driver must be sober and rested, and must carry the original driving licence and
      the vehicle documents.</li>
  <li>The permit is cancelled on any violation of the Picnic Journeys SOP.</li>
  <li>In an emergency call 112 (police) or 108 (ambulance).</li>
</ul>
<p class="small" style="margin-top:8pt">
  {_e(approved)}DC Office, {_e(a.origin_district.name)}, on {_e(_approved_on(a))}.
  Computer generated: it needs no signature. Check that it is genuine by scanning the QR code
  or at {_e(qr.verify_url(a))}
</p>"""
    return _pdf(body, css)


def large_qr_pdf(application: Application) -> bytes:
    """Only the QR code, large, for a windscreen that is tinted or far from the checker."""
    require_permit(application)
    a = application
    code = qr.make(a)
    side = qr.printed_size_cm(code, squares_cm=LARGE_QR_CM)
    css = f"""
.big {{ text-align: center; margin-top: 14pt; }}
.big img {{ width: {side:.2f}cm; height: {side:.2f}cm; }}
.line {{ text-align: center; font-size: 22pt; font-weight: bold; margin: 6pt 0 0; }}
.sub {{ text-align: center; font-size: 13pt; margin: 4pt 0 0; }}
"""
    body = f"""
{_head(a, "Picnic/Recreational Journey Permit: QR code")}
<div class="big"><img src="{qr.svg_data_uri(code)}" alt="QR code of the permit"></div>
<p class="line">{_e(a.vehicle_reg_number)}</p>
<p class="sub">Permit {_e(a.application_number)} · {_e(_day(a.travel_date))} ·
  {_e(_clock(a.departure_time))} to {_e(_clock(a.return_time))}</p>
<p class="sub small">Paste inside the driver's-side windscreen, facing out. Carry the permit
page as well.</p>"""
    return _pdf(body, css)


# ------------------------------------------------------------- application

_ANSWERS = {"YES": "Yes", "NO": "No", "NOT_CHECKED": "Not checked"}


def application_pdf(application: Application, *, status_label: str, office: str) -> bytes:
    """The whole application on paper, for the office file."""
    a = application
    people = "".join(
        f"<tr><td>{p.position}</td><td>{_e(p.name)}"
        f"{' (group leader)' if p.is_group_leader else ''}</td>"
        f"<td>{p.age}</td><td>{_e(p.gender.value.title())}</td></tr>"
        for p in a.passengers
    )
    documents = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            _e(validation.DOCUMENT_LABELS.get(d.doc_type, "Road tax payment proof")),
            _e(d.original_name),
            "Verified" if d.verified else "Not verified" if d.verified is False else "Not checked",
        )
        for d in sorted(a.documents, key=lambda d: d.id)
    )

    findings = a.dto_findings or {}
    dto_rows: list[tuple[str, object]] = [
        (label, _ANSWERS.get((findings.get("vahan") or {}).get(key, ""), "Not checked"))
        for key, label in dto.VAHAN_ITEMS.items()
    ]
    dto_rows += [
        (
            "Challans",
            f"{findings.get('challans_unpaid', '-')} unpaid, "
            f"{findings.get('challans_on_record', '-')} on record",
        ),
    ]
    dto_rows += [
        (label, _ANSWERS.get((findings.get("sarathi") or {}).get(key, ""), "Not checked"))
        for key, label in dto.SARATHI_ITEMS.items()
    ]
    for key, label in (
        ("vahan_remarks", "VAHAN remarks"),
        ("challan_remarks", "Challan remarks"),
        ("sarathi_remarks", "SARATHI remarks"),
    ):
        if findings.get(key):
            dto_rows.append((label, findings[key]))
    inspection = a.inspection or {}
    dto_rows.append(("Inspection", dto.INSPECTION_LABELS[a.inspection_status]))
    if inspection.get("inspected_on"):
        dto_rows.append(
            ("Inspected", f"{inspection['inspected_on']} by {inspection.get('inspecting_officer')}")
        )

    seen = a.police_findings or {}
    police_rows: list[tuple[str, object]] = [
        (
            "Destination police station",
            a.destination_police_station.name if a.destination_police_station else "Not entered",
        ),
        (
            "Driving time",
            police.BAND_LABELS[a.driving_band]
            + (" (confirmed)" if seen.get("driving_time_confirmed") else " (as declared)"),
        ),
        ("Verification remarks", seen.get("verification_remarks", "")),
        ("Checkpoints", seen.get("checkpoints", "")),
        ("Comments for the DC", seen.get("comments", "")),
    ]

    decision: list[tuple[str, object]] = [("Status", f"{status_label} ({office})")]
    if a.status_remarks:
        decision.append(("Remarks", a.status_remarks))
    if a.dc_specific_approval_remark:
        decision.append(("DC's specific approval", a.dc_specific_approval_remark))
    if a.approved_by:
        decision.append(("Approved by", f"{a.approved_by}, on {_approved_on(a)}"))

    body = f"""
{_head(a, "Picnic/Recreational Journey: Application")}
<h2>Decision</h2><table>{_rows(decision)}</table>
<h2>Journey</h2>
<table>{_rows([("Submitted on", _day(a.submission_date)), *_journey_rows(a)])}</table>
<h2>Vehicle and driver</h2>
<table>{
        _rows(
            [
                (
                    "Private or hired",
                    "Private" if a.vehicle_usage.value == "PRIVATE" else "Hired Transport Vehicle",
                ),
                ("Seating capacity", a.seating_capacity),
                ("Owner", f"{a.owner_name}, {a.owner_mobile}"),
                ("Driver's mobile", a.driver_mobile),
                ("Licence", f"{a.licence_class}, valid until {_day(a.licence_valid_until)}"),
                (
                    "Handyman",
                    f"{a.handyman_name}, {a.handyman_mobile}" if a.has_handyman else "None",
                ),
            ]
        )
    }</table>
<h2>Group ({len(a.passengers)} people, without driver and handyman)</h2>
<table><tr><th>No.</th><th>Name</th><th>Age</th><th>Gender</th></tr>{people}</table>
<h2>Documents</h2>
<table><tr><th>Document</th><th>File</th><th>Checked by the DTO</th></tr>{documents}</table>
<h2>DTO: vehicle, driver and inspection</h2><table>{_rows(dto_rows)}</table>
<h2>Police station: group and trip</h2><table>{_rows(police_rows)}</table>
<p class="small" style="margin-top:8pt">Printed from the Picnic Portal. The change log of the
application is on the portal.</p>"""
    return _pdf(body)
