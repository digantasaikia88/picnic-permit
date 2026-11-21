"""The origin police station's own work on an application (PRD Section 7.2).

Verification remarks, the destination police station, the driving time, and
checkpoints and comments for the DC office.
"""

from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.models import Application, DrivingBand, PoliceStation, Status
from app.services import access, audit, sms, validation, workflow
from app.services.access import Acting

BAND_LABELS: dict[DrivingBand, str] = {
    DrivingBand.UP_TO_60: "Up to 60 minutes",
    DrivingBand.FROM_60_TO_90: "60 to 90 minutes",
}


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def record(
    db: Session,
    application: Application,
    *,
    acting: Acting,
    destination_police_station_id: int,
    driving_band: DrivingBand,
    verification_remarks: str,
    checkpoints: str,
    comments: str,
) -> None:
    """Save what the police station verified. It can be saved again until forwarded."""
    access.require_holds(acting.user, application)
    if application.status != Status.PENDING_POLICE:
        raise DomainError("Only the police station can record this.")

    station = db.get(PoliceStation, destination_police_station_id)
    if (
        station is None
        or not station.is_active
        or station.district_id != application.destination_district_id
    ):
        raise DomainError(
            "Choose an active police station of the destination district "
            f"({application.destination_district.name})."
        )

    if not _clean(verification_remarks):
        raise DomainError("Write the verification remarks.")

    old_station = application.destination_police_station
    old_band = application.driving_band
    old_findings = application.police_findings or {}
    old = {
        "destination_police_station": old_station.name if old_station else None,
        "driving_band": BAND_LABELS[old_band],
        "driving_time_confirmed": bool(old_findings.get("driving_time_confirmed")),
        "verification_remarks": old_findings.get("verification_remarks", ""),
        "checkpoints": old_findings.get("checkpoints", ""),
        "comments": old_findings.get("comments", ""),
    }

    findings = {
        "driving_time_confirmed": True,
        "verification_remarks": _clean(verification_remarks),
        "checkpoints": _clean(checkpoints),
        "comments": _clean(comments),
    }
    application.destination_police_station = station
    application.driving_band = driving_band
    application.needs_dc_specific_approval = validation.driving_band_needs_dc_approval(driving_band)
    application.police_findings = findings
    db.flush()

    new = {
        "destination_police_station": station.name,
        "driving_band": BAND_LABELS[driving_band],
        **findings,
    }
    old_changed, new_changed = audit.changed_fields(old, new)
    if not new_changed:
        return
    audit.record(
        db,
        actor=acting.user,
        officer_name=acting.name,
        officer_designation=acting.designation,
        action="application.police_record",
        entity_type="application",
        entity_id=application.id,
        entity_label=application.application_number,
        old=old_changed or None,
        new=new_changed,
    )

    # The applicant is told when the data of the application itself was changed.
    changed = []
    if old_station is not None and old_station.id != station.id:
        changed.append("destination police station")
    if old_band != driving_band:
        changed.append("driving time")
    if changed:
        sms.send(
            db,
            mobile=application.leader_mobile,
            kind=sms.KIND_CORRECTED,
            application=application,
            message=(
                f"Picnic Portal: {application.origin_police_station.name} corrected application "
                f"{application.application_number}: {', '.join(changed)}. "
                f"Status: {workflow.status_url()}"
            ),
        )
