import { z } from "zod";

// The application form: its values, the rules repeated for convenience
// (the backend enforces every one of them), and helpers.

export const DOC_TYPES = [
  "RC",
  "INSURANCE",
  "PUC",
  "VEHICLE_PERMIT",
  "SLD_CERTIFICATE",
  "INSPECTION_CERTIFICATE",
  "OWNER_SELF_CERTIFICATE",
  "DRIVING_LICENCE",
] as const;
export type DocType = (typeof DOC_TYPES)[number];

export type FormConfig = {
  today: string;
  min_travel_date: string;
  max_travel_date: string;
  season: { start_date: string | null; end_date: string | null };
  min_days_before_travel: number;
  max_days_before_travel: number;
  earliest_departure_hour: number;
  latest_return_hour: number;
  leader_min_age: number;
  child_free_below_age: number;
  upload_max_mb: number;
  otp_length: number;
  otp_resend_seconds: number;
  vehicle_types: { id: number; name: string }[];
  documents: { doc_type: DocType; label: string; required: boolean; note: string | null }[];
};

export const GENDERS = [
  { value: "MALE", label: "Male" },
  { value: "FEMALE", label: "Female" },
  { value: "OTHER", label: "Other" },
] as const;

export const KIT_ITEMS = [
  { name: "kit_first_aid", label: "Stocked first-aid kit" },
  { name: "kit_spare_tyre", label: "Usable spare tyre" },
  { name: "kit_jack", label: "Vehicle jack" },
  { name: "kit_spanner", label: "Wheel spanner or wrench" },
  { name: "kit_fire_extinguisher", label: "Fire extinguisher (where available)" },
] as const;

export const VEHICLE_TICKS = [
  {
    name: "decl_not_goods_vehicle",
    label: "This is not a goods vehicle, truck, tractor or trailer.",
  },
  {
    name: "decl_documents_valid",
    label: "All vehicle documents will be valid on the date of travel.",
  },
  {
    name: "decl_no_unpaid_challans",
    label: "There are no unpaid traffic challans on this vehicle.",
  },
] as const;

export const DRIVER_TICKS = [
  {
    name: "decl_licence_valid",
    label: "The licence is valid on the date of travel and is not under suspension.",
  },
  {
    name: "decl_no_conviction",
    label:
      "The driver has no drink-driving or dangerous-driving conviction in the last three years.",
  },
  {
    name: "decl_driver_fit",
    label: "The driver is physically and mentally fit to drive and knows the route.",
  },
] as const;

export const UNDERTAKING_POINTS = [
  "All details and documents given in this application are true.",
  "The journey will not start until final approval is given and the QR code is displayed on the windscreen.",
  "Only the listed vehicle, driver and passengers will travel, on the approved date, to the approved destination.",
  "All members will follow the Picnic Journeys SOP, and I accept responsibility for safe and disciplined conduct throughout the journey.",
];

const uploadSchema = z.object({ token: z.string(), name: z.string(), size: z.number() });
export type Uploaded = z.infer<typeof uploadSchema>;

const memberSchema = z.object({ name: z.string(), age: z.string(), gender: z.string() });
export type Member = z.infer<typeof memberSchema>;

const MOBILE = /^[6-9][0-9]{9}$/;
const WHOLE = /^[0-9]+$/;

function clock(hour: number): string {
  const suffix = hour < 12 ? "AM" : "PM";
  return `${hour % 12 === 0 ? 12 : hour % 12}:00 ${suffix}`;
}

export function formatDay(iso: string): string {
  const [year, month, day] = iso.split("-").map(Number);
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date(year, month - 1, day));
}

/** People counted against the seats: leader, members, driver and handyman. */
export function countPeople(
  values: Pick<FormValues, "leader_age" | "members" | "has_handyman">,
  childFreeBelowAge: number,
): number {
  const ages = [values.leader_age, ...values.members.map((member) => member.age)];
  const counted = ages.filter((age) => !WHOLE.test(age) || Number(age) >= childFreeBelowAge).length;
  return counted + 1 + (values.has_handyman ? 1 : 0);
}

const baseSchema = z.object({
  leader_name: z.string(),
  leader_age: z.string(),
  leader_gender: z.string(),
  leader_mobile: z.string(),
  travel_date: z.string(),
  departure_time: z.string(),
  return_time: z.string(),
  origin_address: z.string(),
  origin_district_id: z.string(),
  origin_police_station_id: z.string(),
  destination_address: z.string(),
  destination_district_id: z.string(),
  destination_police_station_id: z.string(),
  driving_band: z.string(),
  vehicle_reg_number: z.string(),
  vehicle_type_id: z.string(),
  vehicle_usage: z.string(),
  seating_capacity: z.string(),
  owner_name: z.string(),
  owner_mobile: z.string(),
  decl_not_goods_vehicle: z.boolean(),
  decl_documents_valid: z.boolean(),
  decl_no_unpaid_challans: z.boolean(),
  driver_name: z.string(),
  licence_number: z.string(),
  licence_class: z.string(),
  licence_valid_until: z.string(),
  driver_mobile: z.string(),
  decl_licence_valid: z.boolean(),
  decl_no_conviction: z.boolean(),
  decl_driver_fit: z.boolean(),
  has_handyman: z.boolean(),
  handyman_name: z.string(),
  handyman_mobile: z.string(),
  members: z.array(memberSchema),
  kit_first_aid: z.boolean(),
  kit_spare_tyre: z.boolean(),
  kit_jack: z.boolean(),
  kit_spanner: z.boolean(),
  kit_fire_extinguisher: z.boolean(),
  emergency_contacts_saved: z.boolean(),
  undertaking_accepted: z.boolean(),
  documents: z.record(z.string(), uploadSchema.nullable()),
});

export type FormValues = z.infer<typeof baseSchema>;
export type FieldName = keyof FormValues;

export const EMPTY_FORM: FormValues = {
  leader_name: "",
  leader_age: "",
  leader_gender: "",
  leader_mobile: "",
  travel_date: "",
  departure_time: "",
  return_time: "",
  origin_address: "",
  origin_district_id: "",
  origin_police_station_id: "",
  destination_address: "",
  destination_district_id: "",
  destination_police_station_id: "",
  driving_band: "",
  vehicle_reg_number: "",
  vehicle_type_id: "",
  vehicle_usage: "",
  seating_capacity: "",
  owner_name: "",
  owner_mobile: "",
  decl_not_goods_vehicle: false,
  decl_documents_valid: false,
  decl_no_unpaid_challans: false,
  driver_name: "",
  licence_number: "",
  licence_class: "",
  licence_valid_until: "",
  driver_mobile: "",
  decl_licence_valid: false,
  decl_no_conviction: false,
  decl_driver_fit: false,
  has_handyman: false,
  handyman_name: "",
  handyman_mobile: "",
  members: [],
  kit_first_aid: false,
  kit_spare_tyre: false,
  kit_jack: false,
  kit_spanner: false,
  kit_fire_extinguisher: false,
  emergency_contacts_saved: false,
  undertaking_accepted: false,
  documents: {},
};

/** The fields of each step, in order. Used to validate one step and to find a field's step. */
export const STEP_FIELDS: FieldName[][] = [
  [
    "leader_name",
    "leader_age",
    "leader_gender",
    "leader_mobile",
    "travel_date",
    "departure_time",
    "return_time",
    "origin_address",
    "origin_district_id",
    "origin_police_station_id",
  ],
  [
    "destination_address",
    "destination_district_id",
    "destination_police_station_id",
    "driving_band",
  ],
  [
    "vehicle_reg_number",
    "vehicle_type_id",
    "vehicle_usage",
    "seating_capacity",
    "owner_name",
    "owner_mobile",
    "decl_not_goods_vehicle",
    "decl_documents_valid",
    "decl_no_unpaid_challans",
  ],
  [
    "driver_name",
    "licence_number",
    "licence_class",
    "licence_valid_until",
    "driver_mobile",
    "decl_licence_valid",
    "decl_no_conviction",
    "decl_driver_fit",
    "has_handyman",
    "handyman_name",
    "handyman_mobile",
  ],
  ["members"],
  [
    "kit_first_aid",
    "kit_spare_tyre",
    "kit_jack",
    "kit_spanner",
    "kit_fire_extinguisher",
    "emergency_contacts_saved",
    "undertaking_accepted",
  ],
];

export const STEP_TITLES = [
  "Group leader and journey",
  "Destination",
  "Vehicle",
  "Driver and handyman",
  "Passengers",
  "Emergency kit and undertaking",
];

// The driving licence is uploaded in Step 4; all other documents in Step 3.
const STEP_OF_DOCUMENT: Partial<Record<DocType, number>> = { DRIVING_LICENCE: 3 };

/** The step (0 to 5) that holds a field, given a field path such as "members.2.age". */
export function stepOfField(path: string): number {
  const [head, second] = path.split(".");
  if (head === "documents") return STEP_OF_DOCUMENT[second as DocType] ?? 2;
  const index = STEP_FIELDS.findIndex((fields) => fields.includes(head as FieldName));
  return index === -1 ? 0 : index;
}

/** The rules of the form, built from the settings sent by the server. */
export function buildSchema(config: FormConfig) {
  const earliest = `${String(config.earliest_departure_hour).padStart(2, "0")}:00`;
  const latest = `${String(config.latest_return_hour).padStart(2, "0")}:00`;

  return baseSchema.superRefine((v, ctx) => {
    const fail = (path: (string | number)[], message: string) =>
      ctx.addIssue({ code: "custom", path, message });
    const need = (field: FieldName, message: string) => {
      if (typeof v[field] === "string" && !(v[field] as string).trim()) fail([field], message);
    };
    const mobile = (field: FieldName, whose: string) => {
      if (!MOBILE.test(v[field] as string)) fail([field], `Enter ${whose} 10-digit mobile number.`);
    };
    const tick = (field: FieldName, message = "Please confirm this.") => {
      if (!v[field]) fail([field], message);
    };

    // Step 1
    need("leader_name", "Enter the group leader's full name.");
    if (!WHOLE.test(v.leader_age) || Number(v.leader_age) > 120) {
      fail(["leader_age"], "Enter the age in years.");
    } else if (Number(v.leader_age) < config.leader_min_age) {
      fail(["leader_age"], `The group leader must be at least ${config.leader_min_age} years old.`);
    }
    need("leader_gender", "Choose the gender.");
    mobile("leader_mobile", "the group leader's");

    if (!v.travel_date) {
      fail(["travel_date"], "Choose the date of travel.");
    } else if (v.travel_date < config.min_travel_date || v.travel_date > config.max_travel_date) {
      fail(
        ["travel_date"],
        `Choose a date from ${formatDay(config.min_travel_date)} to ${formatDay(config.max_travel_date)}.`,
      );
    }
    if (!v.departure_time) {
      fail(["departure_time"], "Choose the departure time.");
    } else if (v.departure_time < earliest) {
      fail(["departure_time"], `Not before ${clock(config.earliest_departure_hour)}.`);
    }
    if (!v.return_time) {
      fail(["return_time"], "Choose the return time.");
    } else if (v.return_time > latest) {
      fail(["return_time"], `Not after ${clock(config.latest_return_hour)}.`);
    } else if (v.departure_time && v.return_time <= v.departure_time) {
      fail(["return_time"], "Must be later than the departure time.");
    }
    need("origin_address", "Enter the full address of the starting point.");
    need("origin_district_id", "Choose the district.");
    need("origin_police_station_id", "Choose the police station.");

    // Step 2
    need("destination_address", "Enter the full address of the picnic spot.");
    need("destination_district_id", "Choose the district.");
    need("driving_band", "Choose the driving time.");

    // Step 3
    const reg = v.vehicle_reg_number.replace(/[\s-]+/g, "");
    if (reg.length < 5 || reg.length > 12 || !/^[A-Za-z0-9]+$/.test(reg)) {
      fail(["vehicle_reg_number"], "Enter the registration number, for example AS01AB1234.");
    }
    need("vehicle_type_id", "Choose the type of vehicle.");
    need("vehicle_usage", "Choose private or hired.");
    const capacity = Number(v.seating_capacity);
    if (!WHOLE.test(v.seating_capacity) || capacity < 1 || capacity > 100) {
      fail(["seating_capacity"], "Enter the registered seating capacity.");
    }
    need("owner_name", "Enter the owner's name.");
    mobile("owner_mobile", "the owner's");
    for (const rule of config.documents) {
      if (rule.required && !v.documents[rule.doc_type]) {
        fail(["documents", rule.doc_type], "Please upload this document.");
      }
    }
    VEHICLE_TICKS.forEach((item) => tick(item.name));

    // Step 4
    need("driver_name", "Enter the driver's full name.");
    const licence = v.licence_number.replace(/[\s-]+/g, "");
    if (licence.length < 5 || licence.length > 20 || !/^[A-Za-z0-9]+$/.test(licence)) {
      fail(["licence_number"], "Enter the driving licence number as printed on the licence.");
    }
    need("licence_class", "Enter the vehicle class on the licence.");
    if (!v.licence_valid_until) {
      fail(["licence_valid_until"], "Choose the date.");
    } else if (v.travel_date && v.licence_valid_until < v.travel_date) {
      fail(["licence_valid_until"], "The licence must be valid on the date of travel.");
    }
    mobile("driver_mobile", "the driver's");
    DRIVER_TICKS.forEach((item) => tick(item.name));
    if (v.has_handyman) {
      need("handyman_name", "Enter the handyman's name.");
      mobile("handyman_mobile", "the handyman's");
    }

    // Step 5
    if (WHOLE.test(v.seating_capacity)) {
      const people = countPeople(v, config.child_free_below_age);
      if (people > capacity) {
        fail(
          ["members"],
          `${people} people are travelling, counting the group leader, members, driver and handyman, but the vehicle has ${capacity} seats.`,
        );
      }
    }

    // Step 6
    KIT_ITEMS.filter((item) => item.name !== "kit_fire_extinguisher").forEach((item) =>
      tick(item.name, "This item must be carried."),
    );
    tick("emergency_contacts_saved");
    tick("undertaking_accepted", "Please accept the undertaking.");
  });
}

/** The form as the API expects it. */
export function toPayload(v: FormValues) {
  return {
    ...v,
    leader_age: Number(v.leader_age),
    origin_district_id: Number(v.origin_district_id),
    origin_police_station_id: Number(v.origin_police_station_id),
    destination_district_id: Number(v.destination_district_id),
    destination_police_station_id: v.destination_police_station_id
      ? Number(v.destination_police_station_id)
      : null,
    vehicle_type_id: Number(v.vehicle_type_id),
    seating_capacity: Number(v.seating_capacity),
    handyman_name: v.has_handyman ? v.handyman_name : "",
    handyman_mobile: v.has_handyman ? v.handyman_mobile : "",
    members: v.members.map((member) => ({ ...member, age: Number(member.age) })),
    documents: Object.fromEntries(
      Object.entries(v.documents)
        .filter(([, upload]) => upload)
        .map(([docType, upload]) => [docType, upload!.token]),
    ),
  };
}

// ----------------------------------------------- keeping the form on the device
//
// No drafts are saved on the server. Entries are kept in this browser between
// steps, survive a page refresh, and are removed on submission or after a day.

const STORAGE_KEY = "picnic-portal-application-v2";
const KEEP_MS = 24 * 60 * 60 * 1000;

export function loadSaved(): { values: FormValues; step: number } | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const saved = JSON.parse(raw) as { at: number; step: number; values: unknown };
    if (Date.now() - saved.at > KEEP_MS) {
      window.localStorage.removeItem(STORAGE_KEY);
      return null;
    }
    const parsed = baseSchema.safeParse({ ...EMPTY_FORM, ...(saved.values as object) });
    if (!parsed.success) return null;
    return { values: parsed.data, step: Math.min(Math.max(saved.step, 0), 5) };
  } catch {
    return null;
  }
}

export function saveLocally(values: FormValues, step: number): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ at: Date.now(), step, values }));
  } catch {
    // Storage full or blocked: the form still works, it just will not survive a refresh.
  }
}

export function clearSaved(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing to clear.
  }
}

// ------------------------------------------------------------ photo compression

const MAX_SIDE = 1600;
const SKIP_BELOW_BYTES = 300 * 1024;

/**
 * Shrinks a phone photo before upload, for slow connections. PDFs and small
 * pictures are sent as they are. If anything goes wrong, the original is used.
 */
export async function compressPhoto(file: File): Promise<File> {
  if (!file.type.startsWith("image/") || file.size < SKIP_BELOW_BYTES) return file;
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", 0.8),
    );
    if (!blob || blob.size >= file.size) return file;
    return new File([blob], file.name.replace(/\.[^.]+$/, "") + ".jpg", { type: "image/jpeg" });
  } catch {
    return file;
  }
}

export function formatSize(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * The field paths checked when the applicant leaves a step.
 *
 * Documents are listed one by one: the vehicle documents belong to Step 3 and
 * the driving licence to Step 4. Checking all documents on one step would
 * block it over a file that is uploaded on another.
 */
export function stepPaths(step: number, config: FormConfig): string[] {
  const documents = config.documents
    .filter((rule) => stepOfField(`documents.${rule.doc_type}`) === step)
    .map((rule) => `documents.${rule.doc_type}`);
  return [...STEP_FIELDS[step], ...documents];
}

/** The first step (0 to 5) that breaks a rule, or null when the whole form is in order. */
export function firstInvalidStep(
  schema: ReturnType<typeof buildSchema>,
  values: FormValues,
): number | null {
  const result = schema.safeParse(values);
  if (result.success) return null;
  return Math.min(...result.error.issues.map((issue) => stepOfField(issue.path.join("."))));
}
