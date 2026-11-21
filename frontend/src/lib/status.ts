import type { FormValues } from "@/lib/apply";

export type PublicStatus = {
  application_number: string;
  travel_date: string;
  status: string;
  status_label: string;
  current_office: string;
  remarks: string | null;
};

export type ApplicantMe = { mobile: string; expires_in_seconds: number };

export type ApplicationDetail = PublicStatus & {
  submitted_on: string;
  inspection_status: string;
  can_correct: boolean;
  can_upload_inspection_certificate: boolean;
  form: FormValues;
  origin_district: string;
  origin_police_station: string;
  destination_district: string;
  destination_police_station: string | null;
  vehicle_type: string;
  total_people: number;
  passengers: {
    position: number;
    name: string;
    age: number;
    gender: string;
    is_group_leader: boolean;
  }[];
  documents: {
    id: number;
    doc_type: string;
    label: string;
    original_name: string;
    size_bytes: number;
  }[];
};

export const INSPECTION_LABELS: Record<string, string> = {
  CERTIFICATE_UPLOADED: "Certificate uploaded",
  INSPECTION_REQUIRED: "Inspection required",
  INSPECTION_SCHEDULED: "Inspection scheduled",
  PASSED: "Passed",
  FAILED: "Failed",
};

/** Colour of the status label: amber needs the applicant, green is good news, red is closed. */
export function statusTone(status: string): "info" | "warn" | "ok" | "closed" {
  if (status === "RETURNED_TO_APPLICANT" || status === "ON_HOLD_DUPLICATE_CLAIM") return "warn";
  if (status === "APPROVED") return "ok";
  if (status === "REJECTED" || status === "CANCELLED" || status === "EXPIRED") return "closed";
  return "info";
}

export function maskMobile(mobile: string): string {
  return "*".repeat(Math.max(0, mobile.length - 2)) + mobile.slice(-2);
}
