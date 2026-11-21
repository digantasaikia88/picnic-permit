"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { useSession } from "@/components/auth/session";
import { ActionDialog, type ActionSpec } from "@/components/officer/action-dialog";
import { DtoPanel, PolicePanel } from "@/components/officer/office-work";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatIst } from "@/lib/api";
import { formatDay, formatSize, GENDERS } from "@/lib/apply";
import {
  ANSWER_LABELS,
  CHECK_LABELS,
  daysLeft,
  fieldLabel,
  type OfficerDetail,
  type Reference,
  type TimelineEntry,
} from "@/lib/officer";
import { INSPECTION_LABELS } from "@/lib/status";
import { useFetch } from "@/lib/use-fetch";
import { cn } from "@/lib/utils";

const USAGE: Record<string, string> = { PRIVATE: "Private", HIRED: "Hired Transport Vehicle" };
const BANDS: Record<string, string> = {
  UP_TO_60: "Up to 60 minutes",
  FROM_60_TO_90: "60 to 90 minutes",
};

function clock(value: string): string {
  const [hour, minute] = value.split(":").map(Number);
  return `${hour % 12 === 0 ? 12 : hour % 12}:${String(minute).padStart(2, "0")} ${hour < 12 ? "AM" : "PM"}`;
}

function gender(value: string): string {
  return GENDERS.find((item) => item.value === value)?.label ?? value;
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[10rem_1fr] gap-3 py-1.5 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium break-words">{children}</dd>
    </div>
  );
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

/** A logged value in plain words. */
function plain(value: unknown): string {
  if (value === null || value === undefined || value === "") return "(blank)";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string") {
    if (VALUE_WORDS[value]) return VALUE_WORDS[value];
    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return formatDay(value);
    return value;
  }
  if (typeof value === "number") return String(value);
  return JSON.stringify(value);
}

/** Codes kept in the change log, in words. */
const VALUE_WORDS: Record<string, string> = {
  ...ANSWER_LABELS,
  ...CHECK_LABELS,
  ...INSPECTION_LABELS,
};

function Changes({ entry }: { entry: TimelineEntry }) {
  const keys = Object.keys(entry.new_value ?? {})
    .filter((key) => key !== "remarks" && key !== "status")
    // An empty remark that stayed empty is not worth a line.
    .filter((key) => plain(entry.old_value?.[key]) !== plain(entry.new_value?.[key]))
    .sort();
  if (keys.length === 0) return null;
  return (
    <ul className="text-muted-foreground mt-1 space-y-0.5 text-xs">
      {keys.map((key) => (
        <li key={key}>
          {fieldLabel(key)}: {plain(entry.old_value?.[key])} → {plain(entry.new_value?.[key])}
        </li>
      ))}
    </ul>
  );
}

function ApplicationContent() {
  const id = Number((useSearchParams().get("id") ?? "").replace(/\D/g, ""));
  const fetched = useFetch<OfficerDetail>(`/api/officer/applications/${id}`);
  const reference = useFetch<Reference>("/api/officer/reference");
  // After an action the API answers with the updated application.
  const [updated, setUpdated] = useState<OfficerDetail | null>(null);
  const [action, setAction] = useState<ActionSpec | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const { me } = useSession();

  const a = updated ?? fetched.data;
  if (fetched.error && !a) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{fetched.error}</AlertTitle>
        <AlertDescription>
          <Link href="/dashboard">Back to the work queue</Link>
        </AlertDescription>
      </Alert>
    );
  }
  if (!a) return <p className="text-muted-foreground text-sm">Loading…</p>;

  const f = a.form;
  const left = daysLeft(a.days_left);
  const lists = reference.data;

  const actions: Record<string, ActionSpec> = {
    forward: {
      path: "forward",
      title: a.forward_label ?? "Forward",
      description:
        a.status === "PENDING_DC"
          ? "Final approval. The applicant is told by SMS and can then download the permit."
          : "The application moves to the next office and the applicant is told by SMS.",
      confirmLabel: a.forward_label ?? "Forward",
      remarks: {
        label:
          a.status === "PENDING_DC"
            ? "Remarks (optional)"
            : "Remarks for the next office (optional)",
        required: false,
      },
      extra:
        a.status === "PENDING_DC" && a.needs_dc_specific_approval
          ? {
              label: "Specific approval remark",
              field: "specific_approval_remark",
              help: "The driving time is 60 to 90 minutes, which needs the DC’s specific approval.",
            }
          : undefined,
    },
    return: {
      path: "return",
      title: "Return to the applicant",
      description:
        "The applicant sees these remarks, corrects the application and resubmits it. It then comes back to your office.",
      confirmLabel: "Return to the applicant",
      choice: {
        label: "Reason",
        field: "reason_id",
        options: lists?.return_reasons ?? [],
        empty: "Choose a reason",
      },
      remarks: { label: "Remarks for the applicant", required: true },
    },
    reject: {
      path: "reject",
      title: "Reject the application",
      description:
        "The application is closed. The applicant sees the reason and may apply afresh. This cannot be undone.",
      confirmLabel: "Reject",
      destructive: true,
      choice: {
        label: "Reason",
        field: "reason_id",
        options: lists?.reject_reasons ?? [],
        empty: "Choose a reason",
      },
      remarks: { label: "Remarks", required: true },
      tick:
        me.role === "DTO"
          ? {
              label:
                "This is a fake or prank application: flag the mobile number that filed it. Its later applications will show a warning to officers.",
              field: "flag_mobile",
            }
          : undefined,
    },
    working: {
      path: "working-status",
      title: "Set the working status",
      description: "Shown to the applicant on the status page, and in the queues.",
      confirmLabel: "Save",
      choice: {
        label: "Working status",
        field: "working_status_id",
        options: lists?.working_statuses ?? [],
        empty: "Received",
      },
    },
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <p className="text-sm">
            <Link href="/dashboard" className="underline underline-offset-4">
              Work queue
            </Link>
          </p>
          <h1 className="font-mono text-xl font-semibold">{a.application_number}</h1>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Badge>{a.status_label}</Badge>
            {a.working_status && <Badge variant="outline">{a.working_status}</Badge>}
            <span className="text-muted-foreground">Now with: {a.current_office}</span>
          </div>
        </div>
        <div className="text-right text-sm">
          <div className="font-medium">Travel: {formatDay(a.travel_date)}</div>
          {a.status.startsWith("PENDING_") && (
            <div
              className={cn(left.urgent ? "font-semibold text-red-700" : "text-muted-foreground")}
            >
              {left.text}
            </div>
          )}
        </div>
      </div>

      {notice && (
        <Alert>
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      )}

      {a.with_my_office ? (
        <Card>
          <CardHeader>
            <CardTitle>Actions</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {a.forward_blockers.length > 0 && (
              <div className="w-full text-sm text-red-700">
                <p className="font-medium">Before this application can be forwarded:</p>
                <ul className="list-disc pl-5">
                  {a.forward_blockers.map((blocker) => (
                    <li key={blocker}>{blocker}</li>
                  ))}
                </ul>
              </div>
            )}
            <Button
              disabled={a.forward_blockers.length > 0}
              onClick={() => setAction(actions.forward)}
            >
              {a.forward_label}
            </Button>
            <Button variant="outline" onClick={() => setAction(actions.return)}>
              Return to the applicant
            </Button>
            <Button
              variant="outline"
              render={<Link href={`/correct-application?id=${a.id}`} />}
              nativeButton={false}
            >
              Correct data or documents
            </Button>
            <Button variant="outline" onClick={() => setAction(actions.working)}>
              Set working status
            </Button>
            <Button variant="destructive" onClick={() => setAction(actions.reject)}>
              Reject
            </Button>
          </CardContent>
        </Card>
      ) : (
        <Alert>
          <AlertDescription>
            This application is not pending with your office, so you can look at it but not act on
            it.
          </AlertDescription>
        </Alert>
      )}

      {a.status === "ON_HOLD_DUPLICATE_CLAIM" && me.role === "DTO" && (
        <Alert>
          <AlertTitle>This is a duplicate claim on hold</AlertTitle>
          <AlertDescription>
            <Link href="/dashboard/claims" className="underline underline-offset-4">
              Open the duplicate claims list
            </Link>{" "}
            to compare it with the application that blocks it.
          </AlertDescription>
        </Alert>
      )}

      {a.mobile_flag && (
        <Alert variant="destructive">
          <AlertTitle>
            Warning: this mobile number was flagged for a fake or prank application
            {a.mobile_flag.is_blocked ? ", and is now blocked from applying" : ""}
          </AlertTitle>
          <AlertDescription>
            {a.mobile_flag.reason}
            {a.mobile_flag.application_number &&
              ` (application ${a.mobile_flag.application_number})`}
          </AlertDescription>
        </Alert>
      )}

      {a.remarks && (
        <Alert>
          <AlertTitle>{a.status === "REJECTED" ? "Reason for rejection" : "Remarks"}</AlertTitle>
          <AlertDescription>{a.remarks}</AlertDescription>
        </Alert>
      )}

      {a.needs_dc_specific_approval && (
        <Alert>
          <AlertTitle>60 to 90 minutes: needs the DC&rsquo;s specific approval</AlertTitle>
          <AlertDescription>
            The driving time to the picnic spot is 60 to 90 minutes.
            {a.dc_specific_approval_remark &&
              ` Specific approval: ${a.dc_specific_approval_remark}`}
          </AlertDescription>
        </Alert>
      )}

      {a.status !== "ON_HOLD_DUPLICATE_CLAIM" && (
        <DtoPanel
          a={a}
          reference={lists}
          onUpdated={(result, text) => {
            setUpdated(result);
            setNotice(text);
          }}
        />
      )}
      {a.status !== "PENDING_DTO" && a.status !== "ON_HOLD_DUPLICATE_CLAIM" && (
        <PolicePanel
          a={a}
          reference={lists}
          onUpdated={(result, text) => {
            setUpdated(result);
            setNotice(text);
          }}
        />
      )}

      {a.alerts.length > 0 && (
        <Block title={`Alerts (${a.alerts.length})`}>
          <ul className="divide-y text-sm">
            {a.alerts.map((alert) => (
              <li key={alert.application_number} className="space-y-0.5 py-2">
                <div>
                  <span className="font-mono font-medium">{alert.application_number}</span> ·{" "}
                  {formatDay(alert.travel_date)} · {alert.district} · {alert.status_label}
                </div>
                <div className="text-muted-foreground text-xs">
                  Same{" "}
                  {[
                    alert.same_vehicle && "vehicle",
                    alert.same_driver && "driver",
                    alert.same_leader && "group leader's mobile",
                  ]
                    .filter(Boolean)
                    .join(", ")}
                  {alert.rejection_reason && ` · Rejected: ${alert.rejection_reason}`}
                </div>
              </li>
            ))}
          </ul>
        </Block>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Block title="Group leader and journey">
          <dl>
            <Fact label="Group leader">
              {f.leader_name}, {f.leader_age} years, {gender(f.leader_gender)}
            </Fact>
            <Fact label="Mobile number">{f.leader_mobile}</Fact>
            <Fact label="Submitted on">{formatDay(a.submitted_on)}</Fact>
            <Fact label="Date of travel">{formatDay(f.travel_date)}</Fact>
            <Fact label="Hours">
              {clock(f.departure_time)} to {clock(f.return_time)}
            </Fact>
            <Fact label="Starting point">{f.origin_address}</Fact>
            <Fact label="District">{a.origin_district}</Fact>
            <Fact label="Police station">{a.origin_police_station}</Fact>
          </dl>
        </Block>

        <Block title="Destination">
          <dl>
            <Fact label="Picnic spot">{f.destination_address}</Fact>
            <Fact label="District">{a.destination_district}</Fact>
            <Fact label="Police station">{a.destination_police_station ?? "Not given"}</Fact>
            <Fact label="Driving time">{BANDS[f.driving_band] ?? f.driving_band}</Fact>
          </dl>
        </Block>

        <Block title="Vehicle">
          <dl>
            <Fact label="Registration no.">
              <span className="font-mono">{f.vehicle_reg_number}</span>
            </Fact>
            <Fact label="Type">{a.vehicle_type}</Fact>
            <Fact label="Private or hired">{USAGE[f.vehicle_usage] ?? f.vehicle_usage}</Fact>
            <Fact label="Seating capacity">
              {f.seating_capacity} ({a.total_people} travelling)
            </Fact>
            <Fact label="Owner">
              {f.owner_name}, {f.owner_mobile}
            </Fact>
            <Fact label="Inspection">
              {INSPECTION_LABELS[a.inspection_status] ?? a.inspection_status}
            </Fact>
          </dl>
        </Block>

        <Block title="Driver and handyman">
          <dl>
            <Fact label="Driver">
              {f.driver_name}, {f.driver_mobile}
            </Fact>
            <Fact label="Licence no.">
              <span className="font-mono">{f.licence_number}</span>
            </Fact>
            <Fact label="Class">{f.licence_class}</Fact>
            <Fact label="Valid until">{formatDay(f.licence_valid_until)}</Fact>
            <Fact label="Handyman">
              {f.has_handyman ? `${f.handyman_name}, ${f.handyman_mobile}` : "None"}
            </Fact>
          </dl>
        </Block>

        <Block title={`People travelling (${a.total_people}, with driver and handyman)`}>
          <ol className="divide-y text-sm">
            {a.passengers.map((p) => (
              <li key={p.position} className="flex gap-3 py-1.5">
                <span className="text-muted-foreground w-6">{p.position}</span>
                <span>
                  <span className="font-medium">{p.name}</span>
                  <span className="text-muted-foreground">
                    {" "}
                    · {p.is_group_leader ? "Group leader" : "Member"} · {p.age} years,{" "}
                    {gender(p.gender)}
                  </span>
                </span>
              </li>
            ))}
          </ol>
        </Block>

        <Block title="Documents">
          <ul className="divide-y text-sm">
            {a.documents.map((d) => (
              <li key={d.id} className="flex items-center justify-between gap-3 py-2">
                <span className="min-w-0">
                  {d.label}
                  <span className="text-muted-foreground block truncate text-xs">
                    {d.original_name} ({formatSize(d.size_bytes)})
                  </span>
                </span>
                <a
                  href={`/api/officer/applications/${a.id}/documents/${d.id}`}
                  target="_blank"
                  rel="noopener"
                  className="shrink-0 font-medium underline underline-offset-4"
                >
                  Open
                </a>
              </li>
            ))}
          </ul>
        </Block>
      </div>

      <Block title="Timeline">
        <ol className="space-y-3 text-sm">
          {a.timeline.map((entry, index) => (
            <li key={`${entry.at}-${index}`} className="border-l-2 pl-3">
              <div className="font-medium">{entry.title}</div>
              <div className="text-muted-foreground text-xs">
                {formatIst(entry.at)} ·{" "}
                {entry.officer_name
                  ? `${entry.officer_name}, ${entry.officer_designation} (${entry.by})`
                  : entry.by}
              </div>
              {entry.remarks && <div className="mt-1">{entry.remarks}</div>}
              <Changes entry={entry} />
            </li>
          ))}
        </ol>
      </Block>

      {action && (
        <ActionDialog
          spec={action}
          applicationId={a.id}
          onClose={() => setAction(null)}
          onDone={(result) => {
            setAction(null);
            setUpdated(result);
            setNotice(`Done: ${action.title}. The application is now: ${result.status_label}.`);
          }}
        />
      )}
    </div>
  );
}

export default function OfficerApplicationPage() {
  return (
    <Suspense fallback={<p className="text-muted-foreground text-sm">Loading…</p>}>
      <ApplicationContent />
    </Suspense>
  );
}
