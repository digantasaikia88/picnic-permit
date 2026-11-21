"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useRef, useState } from "react";

import { ErrorText, Help, Notice, OutlineButton, Section } from "@/components/apply/fields";
import { OtpGate, type OtpSent } from "@/components/public/otp-gate";
import { Column, PublicPage } from "@/components/public/shell";
import { Fact, StatusCard } from "@/components/public/status-parts";
import { api, errorMessage } from "@/lib/api";
import { compressPhoto, formatDay, formatSize, GENDERS } from "@/lib/apply";
import { INSPECTION_LABELS, type ApplicationDetail } from "@/lib/status";
import { useFetch } from "@/lib/use-fetch";

const USAGE: Record<string, string> = { PRIVATE: "Private", HIRED: "Hired Transport Vehicle" };
const BANDS: Record<string, string> = {
  UP_TO_60: "Up to 60 minutes",
  FROM_60_TO_90: "60 to 90 minutes (needs the DC's specific approval)",
};

function clock(value: string): string {
  const [hour, minute] = value.split(":").map(Number);
  return `${hour % 12 === 0 ? 12 : hour % 12}:${String(minute).padStart(2, "0")} ${hour < 12 ? "AM" : "PM"}`;
}

function genderLabel(value: string): string {
  return GENDERS.find((gender) => gender.value === value)?.label ?? value;
}

function InspectionUpload({ number, onDone }: { number: string; onDone: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function upload(file: File) {
    setBusy(true);
    setProblem(null);
    try {
      const form = new FormData();
      const prepared = await compressPhoto(file);
      form.append("file", prepared, prepared.name);
      await api(`/api/public/my/applications/${number}/inspection-certificate`, {
        method: "POST",
        form,
      });
      setDone(true);
      onDone();
    } catch (error) {
      setProblem(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section title="Upload inspection certificate">
      <Help>
        After the Motor Vehicle Inspector has inspected the vehicle and issued the fitness and
        physical inspection certificate, upload it here. PDF or photo. A new upload replaces the
        earlier one. This is possible only while the application is with the DTO.
      </Help>
      <OutlineButton disabled={busy} onClick={() => input.current?.click()}>
        {busy ? "Uploading…" : "Choose the certificate file"}
      </OutlineButton>
      <input
        ref={input}
        type="file"
        accept="application/pdf,image/jpeg,image/png"
        className="sr-only"
        tabIndex={-1}
        aria-label="Inspection certificate file"
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (file) void upload(file);
        }}
      />
      {done && (
        <p className="text-portal-ok text-[13px] font-medium">The certificate is uploaded.</p>
      )}
      <ErrorText>{problem}</ErrorText>
    </Section>
  );
}

function ApplicationContent() {
  const number = (useSearchParams().get("n") ?? "").replace(/\D/g, "");
  const detail = useFetch<ApplicationDetail>(`/api/public/my/applications/${number}`);
  const [confirmed, setConfirmed] = useState(false);

  // Not confirmed by OTP yet (or the session has ended): ask for the OTP.
  // Someone else's application answers the same way, so nothing leaks.
  if (detail.error && !(confirmed && detail.loading)) {
    return (
      <PublicPage footer>
        <Column>
          <h1 className="text-[22px] leading-tight font-bold">Application {number}</h1>
          <Section title="Confirm by OTP">
            <OtpGate
              intro={
                <>
                  The full application can be seen only by the group leader. We will send an OTP to
                  the group leader&rsquo;s mobile number of this application.
                </>
              }
              confirmLabel="Open the application"
              send={(captcha) =>
                api<OtpSent>("/api/public/status-access/otp", {
                  method: "POST",
                  body: { application_number: number, ...captcha },
                })
              }
              confirm={async (otpId, code) => {
                await api("/api/public/status-access/session", {
                  method: "POST",
                  body: { otp_id: otpId, otp_code: code },
                });
                setConfirmed(true);
                detail.reload();
              }}
            />
          </Section>
          <Link href={`/status?q=${number}`} className="text-portal-blue text-[15px] underline">
            Back to the status search
          </Link>
        </Column>
      </PublicPage>
    );
  }

  const a = detail.data;
  if (!a) {
    return (
      <PublicPage footer>
        <Column>Loading…</Column>
      </PublicPage>
    );
  }
  const f = a.form;

  return (
    <PublicPage footer>
      <Column>
        <h1 className="text-[22px] leading-tight font-bold">Your application</h1>

        <StatusCard item={a}>
          {a.can_correct && (
            <Link
              href={`/status/correct?n=${a.application_number}`}
              className="bg-portal-blue hover:bg-portal-navy flex h-12 items-center justify-center rounded-md px-4 text-base font-semibold text-white"
            >
              Correct and resubmit
            </Link>
          )}
        </StatusCard>

        {a.can_upload_inspection_certificate && (
          <InspectionUpload number={a.application_number} onDone={detail.reload} />
        )}

        <Section title="Group leader and journey">
          <dl className="divide-portal-line divide-y">
            <Fact label="Group leader">
              {f.leader_name}, {f.leader_age} years, {genderLabel(f.leader_gender)}
            </Fact>
            <Fact label="Mobile number">{f.leader_mobile}</Fact>
            <Fact label="Submitted on">{formatDay(a.submitted_on)}</Fact>
            <Fact label="Date of travel">{formatDay(f.travel_date)}</Fact>
            <Fact label="Departure and return">
              {clock(f.departure_time)} to {clock(f.return_time)}
            </Fact>
            <Fact label="Starting point">{f.origin_address}</Fact>
            <Fact label="District and police station">
              {a.origin_district}, {a.origin_police_station}
            </Fact>
          </dl>
        </Section>

        <Section title="Destination">
          <dl className="divide-portal-line divide-y">
            <Fact label="Picnic spot">{f.destination_address}</Fact>
            <Fact label="District and police station">
              {a.destination_district}, {a.destination_police_station ?? "police station not given"}
            </Fact>
            <Fact label="Driving time, one way">{BANDS[f.driving_band] ?? f.driving_band}</Fact>
          </dl>
        </Section>

        <Section title="Vehicle">
          <dl className="divide-portal-line divide-y">
            <Fact label="Registration number">{f.vehicle_reg_number}</Fact>
            <Fact label="Type">
              {a.vehicle_type}, {USAGE[f.vehicle_usage] ?? f.vehicle_usage}
            </Fact>
            <Fact label="Seating capacity">{f.seating_capacity}</Fact>
            <Fact label="Owner">
              {f.owner_name}, {f.owner_mobile}
            </Fact>
            <Fact label="Inspection">
              {INSPECTION_LABELS[a.inspection_status] ?? a.inspection_status}
            </Fact>
          </dl>
        </Section>

        <Section title="Driver and handyman">
          <dl className="divide-portal-line divide-y">
            <Fact label="Driver">
              {f.driver_name}, {f.driver_mobile}
            </Fact>
            <Fact label="Driving licence">
              {f.licence_number}, {f.licence_class}, valid until {formatDay(f.licence_valid_until)}
            </Fact>
            <Fact label="Handyman">
              {f.has_handyman ? `${f.handyman_name}, ${f.handyman_mobile}` : "None"}
            </Fact>
          </dl>
        </Section>

        <Section title={`People travelling (${a.total_people})`}>
          <ol className="flex flex-col">
            {a.passengers.map((p) => (
              <li
                key={p.position}
                className="border-portal-line flex items-baseline gap-2.5 border-b py-2 last:border-b-0"
              >
                <span className="text-portal-muted w-6 text-sm font-semibold">{p.position}</span>
                <span className="text-[15px]">
                  <span className="font-semibold">{p.name}</span>
                  <span className="text-portal-muted">
                    {" "}
                    · {p.is_group_leader ? "Group leader" : "Member"} · {p.age} years,{" "}
                    {genderLabel(p.gender)}
                  </span>
                </span>
              </li>
            ))}
          </ol>
          <Help>
            The count of {a.total_people} includes the driver
            {f.has_handyman ? " and the handyman" : ""}.
          </Help>
        </Section>

        <Section title="Documents">
          <ul className="flex flex-col">
            {a.documents.map((d) => (
              <li
                key={d.id}
                className="border-portal-line flex items-center justify-between gap-3 border-b py-2.5 last:border-b-0"
              >
                <span className="min-w-0 text-[15px] leading-snug">
                  {d.label}
                  <span className="text-portal-muted block truncate text-[13px]">
                    {d.original_name} ({formatSize(d.size_bytes)})
                  </span>
                </span>
                <a
                  href={`/api/public/my/applications/${a.application_number}/documents/${d.id}`}
                  target="_blank"
                  rel="noopener"
                  className="text-portal-blue shrink-0 text-sm font-semibold underline"
                >
                  Open
                </a>
              </li>
            ))}
          </ul>
        </Section>

        <Notice tone="warn" title="This is not permission to travel">
          The journey may start only after final approval, with the QR code displayed on the
          windscreen.
        </Notice>

        <Link href="/status" className="text-portal-blue text-[15px] underline">
          Back to my applications
        </Link>
      </Column>
    </PublicPage>
  );
}

export default function ApplicationPage() {
  // The application number is read from the address, which needs a Suspense boundary.
  return (
    <Suspense
      fallback={
        <PublicPage footer>
          <Column>Loading…</Column>
        </PublicPage>
      }
    >
      <ApplicationContent />
    </Suspense>
  );
}
