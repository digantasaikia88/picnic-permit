"use client";

import { useState } from "react";

import { WorkDialog, ChoiceRow, TextBox } from "@/components/officer/work-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { formatIst } from "@/lib/api";
import { formatDay } from "@/lib/apply";
import {
  ANSWER_LABELS,
  CHECK_LABELS,
  type OfficeDocument,
  type OfficerDetail,
  type Option,
  type Reference,
} from "@/lib/officer";
import { useFetch } from "@/lib/use-fetch";

type PanelProps = {
  a: OfficerDetail;
  reference?: Reference;
  /** Called with the application as the API answers after a change. */
  onUpdated: (updated: OfficerDetail, notice: string) => void;
};

const BANDS: Record<string, string> = {
  UP_TO_60: "Up to 60 minutes",
  FROM_60_TO_90: "60 to 90 minutes",
};

function today(): string {
  // The date in India, whatever the clock of the computer says.
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(new Date());
}

function clock(value: string): string {
  const [hour, minute] = value.split(":").map(Number);
  return `${hour % 12 === 0 ? 12 : hour % 12}:${String(minute).padStart(2, "0")} ${hour < 12 ? "AM" : "PM"}`;
}

function Line({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[11rem_1fr] gap-3 py-1 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="break-words">{children}</dd>
    </div>
  );
}

function Mark({ value }: { value: string }) {
  const tone =
    value === "NO" || value === "NOT_OK"
      ? "font-semibold text-red-700"
      : value === "YES" || value === "OK"
        ? "text-green-700"
        : "text-muted-foreground";
  return <span className={tone}>{ANSWER_LABELS[value] ?? CHECK_LABELS[value] ?? value}</span>;
}

// ------------------------------------------------------------------- DTO

type DtoDialog =
  | { kind: "findings" }
  | { kind: "schedule" }
  | { kind: "result" }
  | { kind: "confirm"; documentId: number | null; of: string }
  | { kind: "verify"; document: OfficeDocument };

/** The DTO's own work: findings, document check, inspection and certificate. */
export function DtoPanel({ a, reference, onUpdated }: PanelProps) {
  const [dialog, setDialog] = useState<DtoDialog | null>(null);
  const canEdit = a.with_my_office && a.status === "PENDING_DTO";
  const base = `/api/officer/applications/${a.id}`;
  const done = (notice: string) => (updated: OfficerDetail) => {
    setDialog(null);
    onUpdated(updated, notice);
  };

  const findings = a.dto_findings;
  const inspection = a.inspection;
  const ownCertificate = a.documents.find((d) => d.doc_type === "INSPECTION_CERTIFICATE");
  const notOk = Object.entries(inspection?.checklist ?? {})
    .filter(([, value]) => value === "NOT_OK")
    .map(([key]) => reference?.checklist_items.find((item) => item.key === key)?.label ?? key);

  return (
    <Card>
      <CardHeader>
        <CardTitle>DTO: vehicle, driver and inspection</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <section className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">VAHAN, challans and SARATHI</h3>
            {canEdit && (
              <Button variant="outline" size="sm" onClick={() => setDialog({ kind: "findings" })}>
                {findings ? "Change findings" : "Record findings"}
              </Button>
            )}
          </div>
          {findings ? (
            <dl>
              {(reference?.vahan_items ?? []).map((item) => (
                <Line key={item.key} label={item.label}>
                  <Mark value={findings.vahan[item.key] ?? "NOT_CHECKED"} />
                </Line>
              ))}
              {findings.vahan_remarks && (
                <Line label="VAHAN remarks">{findings.vahan_remarks}</Line>
              )}
              <Line label="Challans">
                {findings.challans_unpaid ?? "Not checked"} unpaid,{" "}
                {findings.challans_on_record ?? "not checked"} on record
                {a.challan_warning && (
                  <span className="ml-2 font-semibold text-red-700">
                    Warning: 3 or more unpaid challans
                  </span>
                )}
              </Line>
              {findings.challan_remarks && (
                <Line label="Challan remarks">{findings.challan_remarks}</Line>
              )}
              {(reference?.sarathi_items ?? []).map((item) => (
                <Line key={item.key} label={item.label}>
                  <Mark value={findings.sarathi[item.key] ?? "NOT_CHECKED"} />
                </Line>
              ))}
              {findings.sarathi_remarks && (
                <Line label="SARATHI remarks">{findings.sarathi_remarks}</Line>
              )}
            </dl>
          ) : (
            <p className="text-muted-foreground text-sm">Nothing recorded yet.</p>
          )}
        </section>

        <section className="space-y-2">
          <h3 className="text-sm font-semibold">Documents checked against the originals</h3>
          <ul className="divide-y text-sm">
            {a.documents.map((d) => (
              <li key={d.id} className="flex flex-wrap items-center justify-between gap-2 py-1.5">
                <span>{d.label}</span>
                <span className="flex items-center gap-2">
                  {d.verified === true && <Badge>Verified</Badge>}
                  {d.verified === false && <Badge variant="destructive">Not verified</Badge>}
                  {d.verified === null && <Badge variant="outline">Not yet checked</Badge>}
                  {canEdit && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setDialog({ kind: "verify", document: d })}
                    >
                      Mark
                    </Button>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">
              Inspection: <span className="font-normal">{a.inspection_label}</span>
            </h3>
            {canEdit && (
              <span className="flex flex-wrap gap-2">
                {a.inspection_status !== "PASSED" && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setDialog({ kind: "schedule" })}
                  >
                    {inspection?.scheduled_date ? "Change appointment" : "Schedule inspection"}
                  </Button>
                )}
                <Button variant="outline" size="sm" onClick={() => setDialog({ kind: "result" })}>
                  Record inspection result
                </Button>
              </span>
            )}
          </div>
          <dl>
            {inspection?.scheduled_date && (
              <Line label="Appointment">
                {formatDay(inspection.scheduled_date)}
                {inspection.scheduled_time ? `, ${clock(inspection.scheduled_time)}` : ""}
                {inspection.place ? `, at ${inspection.place}` : ""}
              </Line>
            )}
            {inspection?.inspected_on && (
              <>
                <Line label="Inspected on">{formatDay(inspection.inspected_on)}</Line>
                <Line label="Inspecting officer">{inspection.inspecting_officer}</Line>
                <Line label="Not in order">{notOk.length ? notOk.join(", ") : "Nothing"}</Line>
                {inspection.remarks && <Line label="Remarks">{inspection.remarks}</Line>}
              </>
            )}
            <Line label="Certificate">
              {ownCertificate ? (
                <span className="flex flex-wrap items-center gap-2">
                  <a
                    href={`${base}/documents/${ownCertificate.id}`}
                    target="_blank"
                    rel="noopener"
                    className="underline underline-offset-4"
                  >
                    Open the certificate
                  </a>
                  <span className="text-muted-foreground text-xs">
                    {ownCertificate.original_name}
                  </span>
                  {/* Once the vehicle has passed here, nothing more is needed. */}
                  {a.inspection_status !== "PASSED" &&
                    (a.confirmed_certificate_id === ownCertificate.id ? (
                      <>
                        <Badge>Accepted without a new inspection</Badge>
                        {canEdit && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setDialog({ kind: "confirm", documentId: null, of: "" })}
                          >
                            Take back
                          </Button>
                        )}
                      </>
                    ) : (
                      canEdit && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            setDialog({
                              kind: "confirm",
                              documentId: ownCertificate.id,
                              of: "this application",
                            })
                          }
                        >
                          Accept without a new inspection
                        </Button>
                      )
                    ))}
                </span>
              ) : (
                "Not uploaded yet. Upload the certificate you issue in “Record inspection result”."
              )}
              {canEdit && ownCertificate && a.inspection_status !== "PASSED" && (
                <p className="text-muted-foreground mt-1 text-xs">
                  This file was uploaded with the application. If it is a valid certificate for this
                  year, accept it. Otherwise inspect the vehicle and record the result.
                </p>
              )}
            </Line>
          </dl>

          {a.earlier_certificates.length > 0 && (
            <div className="rounded-lg border p-3">
              <p className="text-sm font-medium">Certificates already on record for this vehicle</p>
              <p className="text-muted-foreground text-xs">
                If one is still valid, confirm it and the vehicle need not be inspected again.
              </p>
              <ul className="mt-2 divide-y text-sm">
                {a.earlier_certificates.map((c) => (
                  <li
                    key={c.document_id}
                    className="flex flex-wrap items-center justify-between gap-2 py-1.5"
                  >
                    <span>
                      Application <span className="font-mono">{c.application_number}</span>,
                      uploaded {formatIst(c.uploaded_at)}
                      {c.confirmed && " (confirmed by that DTO)"}
                    </span>
                    <span className="flex items-center gap-2">
                      <a
                        href={`${base}/certificates/${c.document_id}`}
                        target="_blank"
                        rel="noopener"
                        className="underline underline-offset-4"
                      >
                        Open
                      </a>
                      {a.confirmed_certificate_id === c.document_id ? (
                        <Badge>Confirmed</Badge>
                      ) : (
                        canEdit && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() =>
                              setDialog({
                                kind: "confirm",
                                documentId: c.document_id,
                                of: `application ${c.application_number}`,
                              })
                            }
                          >
                            Confirm
                          </Button>
                        )
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      </CardContent>

      {dialog?.kind === "findings" && reference && (
        <FindingsDialog
          a={a}
          reference={reference}
          onClose={() => setDialog(null)}
          onDone={done("Findings saved.")}
        />
      )}
      {dialog?.kind === "schedule" && (
        <ScheduleDialog
          a={a}
          onClose={() => setDialog(null)}
          onDone={done("Inspection scheduled. The applicant is told by SMS.")}
        />
      )}
      {dialog?.kind === "result" && reference && (
        <ResultDialog
          a={a}
          reference={reference}
          onClose={() => setDialog(null)}
          onDone={done("Inspection result saved. The applicant is told by SMS.")}
        />
      )}
      {dialog?.kind === "confirm" && (
        <WorkDialog<OfficerDetail>
          title={
            dialog.documentId === null ? "Take the confirmation back" : "Confirm the certificate"
          }
          description={
            dialog.documentId === null
              ? "The inspection certificate will no longer count as confirmed."
              : `You confirm that the inspection certificate of ${dialog.of} is genuine and valid for this vehicle. The application can then be forwarded.`
          }
          confirmLabel={dialog.documentId === null ? "Take back" : "Confirm"}
          url={`${base}/inspection/confirm-certificate`}
          build={() => ({ document_id: dialog.documentId })}
          onClose={() => setDialog(null)}
          onDone={done(
            dialog.documentId === null ? "Confirmation taken back." : "Certificate confirmed.",
          )}
        >
          {null}
        </WorkDialog>
      )}
      {dialog?.kind === "verify" && (
        <VerifyDialog
          a={a}
          document={dialog.document}
          onClose={() => setDialog(null)}
          onDone={done("Document marked.")}
        />
      )}
    </Card>
  );
}

type DialogProps = {
  a: OfficerDetail;
  onClose: () => void;
  onDone: (updated: OfficerDetail) => void;
};

function FindingsDialog({ a, reference, onClose, onDone }: DialogProps & { reference: Reference }) {
  const old = a.dto_findings;
  const [vahan, setVahan] = useState<Record<string, string>>(old?.vahan ?? {});
  const [sarathi, setSarathi] = useState<Record<string, string>>(old?.sarathi ?? {});
  const [vahanRemarks, setVahanRemarks] = useState(old?.vahan_remarks ?? "");
  const [sarathiRemarks, setSarathiRemarks] = useState(old?.sarathi_remarks ?? "");
  const [challanRemarks, setChallanRemarks] = useState(old?.challan_remarks ?? "");
  const [unpaid, setUnpaid] = useState(old?.challans_unpaid?.toString() ?? "");
  const [onRecord, setOnRecord] = useState(old?.challans_on_record?.toString() ?? "");
  const number = (value: string) => (value.trim() === "" ? null : Number(value));

  return (
    <WorkDialog<OfficerDetail>
      wide
      title="VAHAN, challan and SARATHI findings"
      description="Check from the DTO's own access, and record what you found. You can save part of it and finish later, but every item needs a Yes or No, and the challan numbers, before the application can be forwarded."
      confirmLabel="Save findings"
      url={`/api/officer/applications/${a.id}/dto-findings`}
      build={() => ({
        vahan,
        vahan_remarks: vahanRemarks,
        challans_unpaid: number(unpaid),
        challans_on_record: number(onRecord),
        challan_remarks: challanRemarks,
        sarathi,
        sarathi_remarks: sarathiRemarks,
      })}
      onClose={onClose}
      onDone={onDone}
    >
      <h3 className="text-sm font-semibold">
        Vehicle {a.vehicle_reg_number} in VAHAN: is it in order?
      </h3>
      <div>
        {reference.vahan_items.map((item) => (
          <ChoiceRow
            key={item.key}
            label={item.label}
            value={vahan[item.key] ?? "NOT_CHECKED"}
            options={ANSWER_LABELS}
            onChange={(value) => setVahan({ ...vahan, [item.key]: value })}
          />
        ))}
      </div>
      <TextBox label="VAHAN remarks" value={vahanRemarks} onChange={setVahanRemarks} />

      <h3 className="pt-2 text-sm font-semibold">Challans on the vehicle</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="challans-unpaid">Number unpaid</Label>
          <Input
            id="challans-unpaid"
            inputMode="numeric"
            pattern="[0-9]*"
            value={unpaid}
            onChange={(event) => setUnpaid(event.target.value.replace(/\D/g, ""))}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="challans-record">Number on record</Label>
          <Input
            id="challans-record"
            inputMode="numeric"
            pattern="[0-9]*"
            value={onRecord}
            onChange={(event) => setOnRecord(event.target.value.replace(/\D/g, ""))}
          />
        </div>
      </div>
      <TextBox label="Challan remarks" value={challanRemarks} onChange={setChallanRemarks} />

      <h3 className="pt-2 text-sm font-semibold">
        Driver ({String(a.form.licence_number)}) in SARATHI
      </h3>
      <div>
        {reference.sarathi_items.map((item) => (
          <ChoiceRow
            key={item.key}
            label={item.label}
            value={sarathi[item.key] ?? "NOT_CHECKED"}
            options={ANSWER_LABELS}
            onChange={(value) => setSarathi({ ...sarathi, [item.key]: value })}
          />
        ))}
      </div>
      <TextBox label="SARATHI remarks" value={sarathiRemarks} onChange={setSarathiRemarks} />
    </WorkDialog>
  );
}

function ScheduleDialog({ a, onClose, onDone }: DialogProps) {
  const [on, setOn] = useState(a.inspection?.scheduled_date ?? "");
  const [at, setAt] = useState(a.inspection?.scheduled_time ?? "10:00");
  const [place, setPlace] = useState(a.inspection?.place ?? "");
  return (
    <WorkDialog<OfficerDetail>
      title="Schedule the vehicle inspection"
      description="The applicant gets an SMS with the date, time and place, asking that the vehicle be brought with the original documents."
      confirmLabel="Schedule and send SMS"
      url={`/api/officer/applications/${a.id}/inspection/schedule`}
      build={() => ({ on, at, place })}
      onClose={onClose}
      onDone={onDone}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="inspection-date">Date</Label>
          <Input
            id="inspection-date"
            type="date"
            required
            min={today()}
            max={a.travel_date}
            value={on}
            onChange={(event) => setOn(event.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="inspection-time">Time</Label>
          <Input
            id="inspection-time"
            type="time"
            required
            value={at}
            onChange={(event) => setAt(event.target.value)}
          />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="inspection-place">Place</Label>
        <Input
          id="inspection-place"
          required
          maxLength={200}
          value={place}
          onChange={(event) => setPlace(event.target.value)}
          placeholder="For example: DTO office, Tinsukia"
        />
      </div>
    </WorkDialog>
  );
}

function ResultDialog({ a, reference, onClose, onDone }: DialogProps & { reference: Reference }) {
  const [checklist, setChecklist] = useState<Record<string, string>>(a.inspection?.checklist ?? {});
  const [inspectedOn, setInspectedOn] = useState(a.inspection?.inspected_on ?? today());
  const [inspector, setInspector] = useState(a.inspection?.inspecting_officer ?? "");
  // A result recorded earlier is shown again, so that the certificate can be added later.
  const recorded = a.inspection?.inspected_on ? a.inspection_status : "";
  const [result, setResult] = useState(
    recorded === "PASSED" || recorded === "FAILED" ? recorded : "",
  );
  const [remarks, setRemarks] = useState(a.inspection?.remarks ?? "");
  const [file, setFile] = useState<File | null>(null);
  const hasCertificate = a.documents.some((d) => d.doc_type === "INSPECTION_CERTIFICATE");
  const withFile = result === "PASSED" && file !== null;

  return (
    <WorkDialog<OfficerDetail>
      wide
      title="Inspection checklist and result"
      description={`Physical inspection and fitness test of vehicle ${a.vehicle_reg_number}. The applicant is told the result by SMS.`}
      confirmLabel="Save result"
      url={`/api/officer/applications/${a.id}/inspection/${withFile ? "result-with-certificate" : "result"}`}
      build={() => {
        const unmarked = reference.checklist_items.find((item) => !checklist[item.key]);
        if (unmarked) return `Mark every item of the checklist. Not marked: ${unmarked.label}.`;
        if (!result) return "Choose the result: passed or failed.";
        const body = {
          checklist,
          inspected_on: inspectedOn,
          inspecting_officer: inspector,
          passed: result === "PASSED",
          remarks,
        };
        if (!withFile || !file) return body;
        // With the scanned certificate, the result goes as a form that carries the file.
        const form = new FormData();
        form.append("data", JSON.stringify(body));
        form.append("file", file);
        return form;
      }}
      onClose={onClose}
      onDone={onDone}
    >
      <div>
        {reference.checklist_items.map((item) => (
          <ChoiceRow
            key={item.key}
            label={item.label}
            value={checklist[item.key] ?? ""}
            options={CHECK_LABELS}
            onChange={(value) => setChecklist({ ...checklist, [item.key]: value })}
          />
        ))}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="inspected-on">Date of inspection</Label>
          <Input
            id="inspected-on"
            type="date"
            required
            max={today()}
            value={inspectedOn}
            onChange={(event) => setInspectedOn(event.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="inspector">Inspecting officer</Label>
          <Input
            id="inspector"
            required
            maxLength={100}
            value={inspector}
            onChange={(event) => setInspector(event.target.value)}
          />
        </div>
      </div>
      <ChoiceRow
        label="Result"
        value={result}
        options={{ PASSED: "Passed", FAILED: "Failed" }}
        onChange={setResult}
      />
      {result === "PASSED" && (
        <div className="space-y-1.5">
          <Label htmlFor="issued-certificate">
            Fitness and physical inspection certificate issued (scan: PDF, JPG or PNG)
          </Label>
          <Input
            id="issued-certificate"
            type="file"
            accept="application/pdf,image/jpeg,image/png"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
          <p className="text-muted-foreground text-xs">
            {hasCertificate
              ? "It takes the place of the certificate now on the application, in the Documents list as well."
              : "It is added to the Documents of the application."}{" "}
            You can also save the result now and add the scan later from this same form.
          </p>
        </div>
      )}
      <TextBox label="Remarks" value={remarks} onChange={setRemarks} />
    </WorkDialog>
  );
}

function VerifyDialog({
  a,
  document,
  onClose,
  onDone,
}: DialogProps & { document: OfficeDocument }) {
  const [value, setValue] = useState(
    document.verified === null ? "" : document.verified ? "YES" : "NO",
  );
  return (
    <WorkDialog<OfficerDetail>
      title={document.label}
      description="Compare the uploaded copy with the original document."
      confirmLabel="Save"
      url={`/api/officer/applications/${a.id}/documents/${document.id}/verify`}
      build={() => ({ verified: value === "" ? null : value === "YES" })}
      onClose={onClose}
      onDone={onDone}
    >
      <ChoiceRow
        label="Checked against the original"
        value={value}
        options={{ YES: "Verified", NO: "Not verified", "": "Not yet checked" }}
        onChange={setValue}
      />
    </WorkDialog>
  );
}

// ---------------------------------------------------------------- police

/** The police station's own work: verification, destination station, transfer. */
export function PolicePanel({ a, reference, onUpdated }: PanelProps) {
  const [dialog, setDialog] = useState<"record" | "transfer" | null>(null);
  const canEdit = a.with_my_office && a.status === "PENDING_POLICE";
  const findings = a.police_findings;
  const done = (notice: string) => (updated: OfficerDetail) => {
    setDialog(null);
    onUpdated(updated, notice);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Police station: group and trip</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {canEdit && (
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => setDialog("record")}>
              {findings ? "Change verification" : "Record verification"}
            </Button>
            <Button variant="outline" size="sm" onClick={() => setDialog("transfer")}>
              Transfer to another police station
            </Button>
          </div>
        )}
        <dl>
          <Line label="Destination police station">
            {a.destination_police_station ?? (
              <span className="font-semibold text-red-700">
                Not entered. It must be entered before forwarding.
              </span>
            )}
          </Line>
          <Line label="Driving time">
            {BANDS[String(a.form.driving_band)] ?? String(a.form.driving_band)}
            {findings?.driving_time_confirmed
              ? " (confirmed by the police station)"
              : " (as declared; not yet confirmed)"}
          </Line>
          {findings?.verification_remarks && (
            <Line label="Verification remarks">{findings.verification_remarks}</Line>
          )}
          {findings?.checkpoints && <Line label="Checkpoints">{findings.checkpoints}</Line>}
          {findings?.comments && <Line label="Comments for the DC">{findings.comments}</Line>}
        </dl>
      </CardContent>

      {dialog === "record" && (
        <PoliceRecordDialog
          a={a}
          onClose={() => setDialog(null)}
          onDone={done("Verification saved.")}
        />
      )}
      {dialog === "transfer" && (
        <TransferDialog
          a={a}
          stations={reference?.police_stations ?? []}
          onClose={() => setDialog(null)}
          onDone={done("Transferred. The applicant is told by SMS.")}
        />
      )}
    </Card>
  );
}

function PoliceRecordDialog({ a, onClose, onDone }: DialogProps) {
  const stations = useFetch<Option[]>(
    `/api/public/police-stations?district_id=${a.form.destination_district_id}`,
  );
  const old = a.police_findings;
  const [station, setStation] = useState(String(a.form.destination_police_station_id ?? ""));
  const [band, setBand] = useState(String(a.form.driving_band));
  const [remarks, setRemarks] = useState(old?.verification_remarks ?? "");
  const [checkpoints, setCheckpoints] = useState(old?.checkpoints ?? "");
  const [comments, setComments] = useState(old?.comments ?? "");

  return (
    <WorkDialog<OfficerDetail>
      wide
      title="Police verification"
      description="Verify the picnic group and the trip. The destination police station then sees the journey in its incoming list."
      confirmLabel="Save verification"
      url={`/api/officer/applications/${a.id}/police-record`}
      build={() => {
        if (!station) return "Choose the destination police station.";
        if (!remarks.trim()) return "Write the verification remarks.";
        return {
          destination_police_station_id: Number(station),
          driving_band: band,
          verification_remarks: remarks,
          checkpoints,
          comments,
        };
      }}
      onClose={onClose}
      onDone={onDone}
    >
      <div className="space-y-1.5">
        <Label htmlFor="destination-station">
          Destination police station ({a.destination_district})
        </Label>
        <NativeSelect
          id="destination-station"
          className="w-full"
          value={station}
          onChange={(event) => setStation(event.target.value)}
        >
          <NativeSelectOption value="">Choose a police station</NativeSelectOption>
          {(stations.data ?? []).map((option) => (
            <NativeSelectOption key={option.id} value={option.id}>
              {option.name}
            </NativeSelectOption>
          ))}
        </NativeSelect>
        <p className="text-muted-foreground text-xs">Picnic spot: {a.destination}</p>
      </div>
      <ChoiceRow
        label="Driving time to the picnic spot"
        value={band}
        options={BANDS}
        onChange={setBand}
      />
      <p className="text-muted-foreground text-xs">
        Saving confirms the driving time. 60 to 90 minutes needs the DC&rsquo;s specific approval. A
        spot beyond 90 minutes cannot be approved: reject the application.
      </p>
      <TextBox label="Verification remarks" value={remarks} onChange={setRemarks} />
      <TextBox label="Checkpoints on the route" value={checkpoints} onChange={setCheckpoints} />
      <TextBox
        label="Safety or law-and-order comments for the DC office"
        value={comments}
        onChange={setComments}
      />
    </WorkDialog>
  );
}

function TransferDialog({ a, stations, onClose, onDone }: DialogProps & { stations: Option[] }) {
  const [station, setStation] = useState("");
  const [remarks, setRemarks] = useState("");
  const others = stations.filter((option) => option.name !== a.origin_police_station);
  return (
    <WorkDialog<OfficerDetail>
      title="Transfer to another police station"
      description="Use this when the starting point is under another police station of the same district. The application leaves your queue."
      confirmLabel="Transfer"
      url={`/api/officer/applications/${a.id}/transfer`}
      build={() => {
        if (!station) return "Choose the police station.";
        if (!remarks.trim()) return "Write the reason for the transfer.";
        return { police_station_id: Number(station), remarks };
      }}
      onClose={onClose}
      onDone={onDone}
    >
      <div className="space-y-1.5">
        <Label htmlFor="transfer-station">Correct police station</Label>
        <NativeSelect
          id="transfer-station"
          className="w-full"
          value={station}
          onChange={(event) => setStation(event.target.value)}
        >
          <NativeSelectOption value="">Choose a police station</NativeSelectOption>
          {others.map((option) => (
            <NativeSelectOption key={option.id} value={option.id}>
              {option.name}
            </NativeSelectOption>
          ))}
        </NativeSelect>
      </div>
      <TextBox label="Reason for the transfer" value={remarks} onChange={setRemarks} />
    </WorkDialog>
  );
}
