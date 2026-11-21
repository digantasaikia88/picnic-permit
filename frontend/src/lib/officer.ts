import type { FormValues } from "@/lib/apply";

// Types and helpers of the officer screens.

/** The person taking an action. An office may share one user ID, so each action names them. */
export type Officer = { name: string; designation: string };

const OFFICER_KEY = "picnic-portal-officer";

/** The name and designation typed last on this computer, so they are typed once. */
export function loadOfficer(): Officer {
  try {
    const saved = JSON.parse(window.localStorage.getItem(OFFICER_KEY) ?? "{}") as Partial<Officer>;
    return { name: saved.name ?? "", designation: saved.designation ?? "" };
  } catch {
    return { name: "", designation: "" };
  }
}

export function saveOfficer(officer: Officer): void {
  try {
    window.localStorage.setItem(
      OFFICER_KEY,
      JSON.stringify({ name: officer.name.trim(), designation: officer.designation.trim() }),
    );
  } catch {
    // Not remembered: the officer types it again next time.
  }
}

export type QueueItem = {
  id: number;
  application_number: string;
  travel_date: string;
  days_left: number;
  status: string;
  status_label: string;
  working_status: string | null;
  current_office: string;
  leader_name: string;
  leader_mobile: string;
  vehicle_reg_number: string;
  origin_police_station: string;
  destination: string;
  total_people: number;
  needs_dc_specific_approval: boolean;
  inspection_status: string;
  is_duplicate_claim: boolean;
  /** The group leader's mobile number was flagged for a fake or prank application. */
  mobile_flagged: boolean;
  with_my_office: boolean;
};

export type Alert = {
  application_number: string;
  travel_date: string;
  status: string;
  status_label: string;
  district: string;
  same_vehicle: boolean;
  same_driver: boolean;
  same_leader: boolean;
  rejection_reason: string | null;
};

export type TimelineEntry = {
  at: string;
  action: string;
  title: string;
  by: string;
  officer_name: string | null;
  officer_designation: string | null;
  remarks: string | null;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
};

export type OfficerDetail = QueueItem & {
  submitted_on: string;
  remarks: string | null;
  forward_label: string | null;
  form: FormValues;
  origin_district: string;
  destination_district: string;
  destination_police_station: string | null;
  vehicle_type: string;
  passengers: {
    position: number;
    name: string;
    age: number;
    gender: string;
    is_group_leader: boolean;
  }[];
  documents: OfficeDocument[];
  alerts: Alert[];
  timeline: TimelineEntry[];
  /** What still stops the office from forwarding. Empty when it can forward. */
  forward_blockers: string[];
  mobile_flag: { reason: string; application_number: string | null; is_blocked: boolean } | null;
  dto_findings: DtoFindings | null;
  challan_warning: boolean;
  inspection: Inspection | null;
  inspection_label: string;
  certificate_confirmed: boolean;
  confirmed_certificate_id: number | null;
  earlier_certificates: EarlierCertificate[];
  police_findings: PoliceFindings | null;
  dc_specific_approval_remark: string | null;
};

export type OfficeDocument = {
  id: number;
  doc_type: string;
  label: string;
  original_name: string;
  size_bytes: number;
  /** Checked by the DTO against the original. Empty: not yet checked. */
  verified: boolean | null;
};

export type Answer = "YES" | "NO" | "NOT_CHECKED";
export const ANSWER_LABELS: Record<string, string> = {
  YES: "Yes",
  NO: "No",
  NOT_CHECKED: "Not checked",
};

export type DtoFindings = {
  vahan: Record<string, Answer>;
  vahan_remarks: string;
  challans_unpaid: number | null;
  challans_on_record: number | null;
  challan_remarks: string;
  sarathi: Record<string, Answer>;
  sarathi_remarks: string;
};

export type CheckAnswer = "OK" | "NOT_OK" | "NOT_APPLICABLE";
export const CHECK_LABELS: Record<string, string> = {
  OK: "In order",
  NOT_OK: "Not in order",
  NOT_APPLICABLE: "Does not apply",
};

export type Inspection = {
  scheduled_date?: string | null;
  scheduled_time?: string | null;
  place?: string | null;
  checklist?: Record<string, CheckAnswer>;
  inspected_on?: string;
  inspecting_officer?: string;
  remarks?: string;
};

export type EarlierCertificate = {
  document_id: number;
  application_number: string;
  travel_date: string;
  uploaded_at: string;
  original_name: string;
  confirmed: boolean;
};

export type PoliceFindings = {
  driving_time_confirmed: boolean;
  verification_remarks: string;
  checkpoints: string;
  comments: string;
};

export type Option = { id: number; name: string };
export type ChoiceItem = { key: string; label: string };

export type Reference = {
  working_statuses: Option[];
  return_reasons: Option[];
  reject_reasons: Option[];
  vahan_items: ChoiceItem[];
  sarathi_items: ChoiceItem[];
  checklist_items: ChoiceItem[];
  /** Police stations of the user's own district, for a transfer. */
  police_stations: Option[];
  duplicate_claims: number;
};

/** One of the two applications the DTO compares in a duplicate claim. */
export type ClaimSide = {
  id: number;
  application_number: string;
  status: string;
  status_label: string;
  current_office: string;
  district: string;
  submitted_at: string;
  travel_date: string;
  leader_name: string;
  leader_mobile: string;
  mobile_flagged: boolean;
  owner_name: string;
  owner_mobile: string;
  vehicle_reg_number: string;
  driver_name: string;
  licence_number: string;
  driver_mobile: string;
  same_vehicle: boolean;
  same_driver: boolean;
  documents: OfficeDocument[];
};

export type Claim = { claim: ClaimSide; blocking: ClaimSide[] };

export type FlaggedMobile = {
  id: number;
  mobile: string;
  reason: string;
  application_number: string | null;
  flagged_by: string;
  is_blocked: boolean;
  created_at: string;
};

/** Days to the travel date, in words, and whether it is close enough to highlight. */
export function daysLeft(days: number): { text: string; urgent: boolean } {
  if (days < 0) return { text: "Travel date passed", urgent: true };
  if (days === 0) return { text: "Travels today", urgent: true };
  if (days === 1) return { text: "1 day left", urgent: true };
  return { text: `${days} days left`, urgent: days <= 3 };
}

/** Names of the logged fields, as the timeline shows them. */
const FIELD_NAMES: Record<string, string> = {
  working_status: "Working status",
  leader_name: "Group leader's name",
  leader_age: "Group leader's age",
  leader_gender: "Group leader's gender",
  travel_date: "Date of travel",
  departure_time: "Departure time",
  return_time: "Return time",
  origin_address: "Starting point",
  origin_district_id: "District of starting point",
  origin_police_station_id: "Police station of starting point",
  destination_address: "Picnic spot",
  destination_district_id: "Destination district",
  destination_police_station_id: "Destination police station",
  driving_band: "Driving time",
  vehicle_reg_number: "Vehicle registration number",
  vehicle_type_id: "Type of vehicle",
  vehicle_usage: "Private or hired",
  seating_capacity: "Seating capacity",
  owner_name: "Owner's name",
  owner_mobile: "Owner's mobile number",
  driver_name: "Driver's name",
  licence_number: "Driving licence number",
  licence_class: "Licence class",
  licence_valid_until: "Licence validity",
  driver_mobile: "Driver's mobile number",
  has_handyman: "Handyman",
  handyman_name: "Handyman's name",
  handyman_mobile: "Handyman's mobile number",
  passengers: "Passenger list",
  documents_replaced: "Documents replaced",
  dto_office: "DTO office",
};

/** Beginnings of logged names that come in groups, such as "vahan.insurance". */
const GROUP_NAMES: Record<string, string> = {
  vahan: "VAHAN",
  sarathi: "SARATHI",
  checklist: "Checklist",
  verified: "Verified",
};

/** Short names in the change log that read badly as they are. */
const ITEM_NAMES: Record<string, string> = {
  rc: "registration certificate",
  RC: "registration certificate",
  puc: "PUC certificate",
  PUC: "PUC certificate",
  tax: "road tax",
  sld: "Speed Limiting Device",
  doors: "doors and emergency exits",
  lights: "lights and indicators",
  tyres: "tyres, including the spare",
  no_suspension: "no suspension",
  no_convictions: "no disqualifying conviction",
  OWNER_SELF_CERTIFICATE: "owner's self-certificate",
  DRIVING_LICENCE: "driving licence",
  INSPECTION_CERTIFICATE: "inspection certificate",
  INSURANCE: "insurance",
  VEHICLE_PERMIT: "vehicle permit",
  SLD_CERTIFICATE: "SLD certificate",
};

export function fieldLabel(key: string): string {
  const [group, item] = key.split(".");
  if (item && GROUP_NAMES[group]) {
    const name = ITEM_NAMES[item] ?? item.replaceAll("_", " ").toLowerCase();
    return `${GROUP_NAMES[group]}: ${name}`;
  }
  const fallback = key.replace(/_id$/, "").replaceAll("_", " ");
  return FIELD_NAMES[key] ?? fallback.charAt(0).toUpperCase() + fallback.slice(1);
}
