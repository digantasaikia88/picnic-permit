import { z } from "zod";

// All API calls use relative URLs. Next.js (development) or Nginx (production)
// forwards /api to the backend, so the browser never needs the backend's address.

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    /** Row-level problems of a bulk upload. */
    readonly errors: string[] = [],
    /** Messages for individual form fields, keyed by field name. */
    readonly fieldErrors: Record<string, string> = {},
  ) {
    super(message);
  }
}

type Options = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  /** Sent as JSON. */
  body?: unknown;
  /** Sent as a multipart form (file uploads). */
  form?: FormData;
  signal?: AbortSignal;
};

async function request(path: string, options: Options = {}): Promise<Response> {
  const headers: Record<string, string> = {
    // The API refuses state-changing requests without this header (see the backend).
    "X-Requested-With": "fetch",
  };
  let body: BodyInit | undefined;
  if (options.form) {
    body = options.form;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  const response = await fetch(path, {
    method: options.method ?? "GET",
    headers,
    body,
    cache: "no-store",
    credentials: "same-origin",
    signal: options.signal,
  });
  if (response.ok) return response;

  let message = `The request failed (status ${response.status}).`;
  let errors: string[] = [];
  let fieldErrors: Record<string, string> = {};
  try {
    const data: unknown = await response.json();
    if (data && typeof data === "object") {
      const detail = (data as { detail?: unknown }).detail;
      if (typeof detail === "string") {
        message = detail;
      } else if (Array.isArray(detail)) {
        // Field validation errors from the API.
        message = detail
          .map((item) =>
            item && typeof item === "object" && "msg" in item ? String(item.msg) : "",
          )
          .filter(Boolean)
          .join(" ");
      }
      const rowErrors = (data as { errors?: unknown }).errors;
      if (Array.isArray(rowErrors)) errors = rowErrors.map(String);
      const fields = (data as { field_errors?: unknown }).field_errors;
      if (fields && typeof fields === "object") fieldErrors = fields as Record<string, string>;
    }
  } catch {
    // Not JSON: keep the generic message.
  }
  throw new ApiError(message, response.status, errors, fieldErrors);
}

export async function api<T>(path: string, options?: Options): Promise<T> {
  const response = await request(path, options);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Calls the API and saves the answer as a file (Excel downloads). */
export async function download(path: string, options?: Options): Promise<void> {
  const response = await request(path, options);
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? "download.xlsx";
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

// ------------------------------------------------------------------- health

export const healthSchema = z.object({
  status: z.enum(["ok", "degraded"]),
  database: z.enum(["ok", "unreachable"]),
  environment: z.enum(["development", "production"]),
  checked_at: z.string(),
});

export type Health = z.infer<typeof healthSchema>;

/**
 * Calls GET /api/health. A 503 still carries a valid body (database unreachable),
 * so it is returned rather than thrown. Throws only when the API itself cannot be reached.
 */
export async function getHealth(signal?: AbortSignal): Promise<Health> {
  const response = await fetch("/api/health", { cache: "no-store", signal });
  if (!response.ok && response.status !== 503) {
    throw new Error(`The API answered with status ${response.status}`);
  }
  return healthSchema.parse(await response.json());
}

// -------------------------------------------------------------------- types

export type Role = "STATE_ADMIN" | "DTO" | "POLICE_STATION" | "DC_OFFICE" | "VIEWER";

export const ROLE_LABELS: Record<Role, string> = {
  STATE_ADMIN: "State Admin",
  DTO: "DTO",
  POLICE_STATION: "Police Station",
  DC_OFFICE: "DC Office",
  VIEWER: "Viewer",
};

export type Me = {
  id: number;
  user_id: string;
  role: Role;
  office: string;
  must_change_password: boolean;
  jurisdiction_level: "STATE" | "DISTRICT" | "POLICE_STATION";
  district_id: number | null;
  district_name: string | null;
  police_station_id: number | null;
  police_station_name: string | null;
};

export type Captcha = { enabled: boolean; captcha_id: string | null; image: string | null };

export type District = {
  id: number;
  code: number;
  name: string;
  short_name: string;
  is_active: boolean;
};

export type PoliceStation = { id: number; name: string; district_id: number; is_active: boolean };

export type DtoOffice = {
  id: number;
  code: string;
  name: string;
  district_id: number;
  is_active: boolean;
};

export type UserStatus = "ACTIVE" | "INACTIVE" | "LOCKED" | "NO_PASSWORD" | "MUST_CHANGE_PASSWORD";

export type User = {
  id: number;
  user_id: string;
  role: Role;
  office: string;
  district_id: number | null;
  district_name: string | null;
  police_station_id: number | null;
  dto_office_id: number | null;
  status: UserStatus;
  is_active: boolean;
  last_login_at: string | null;
};

export type Page<T> = { items: T[]; total: number; page: number; page_size: number };

export type UserWithPassword = { user: User; password: string };

export type Setting = {
  key: string;
  value: number;
  description: string;
  min_value: number;
  max_value: number;
};

export type AuditRow = {
  id: number;
  at: string;
  actor: string;
  action: string;
  entity_type: string;
  entity_label: string | null;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
};

/** Where an officer lands after logging in. */
export function homePathFor(me: Pick<Me, "role" | "must_change_password">): string {
  if (me.must_change_password) return "/change-password";
  return me.role === "STATE_ADMIN" ? "/admin" : "/dashboard";
}

const istFormat = new Intl.DateTimeFormat("en-IN", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Asia/Kolkata",
});

/** Shows a stored UTC time in Indian Standard Time. */
export function formatIst(value: string | null): string {
  return value ? istFormat.format(new Date(value)) : "";
}
