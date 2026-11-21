"use client";

import Link from "next/link";
import { useState } from "react";

import { useSession } from "@/components/auth/session";
import { TextBox, WorkDialog } from "@/components/officer/work-dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { formatIst } from "@/lib/api";
import { formatDay } from "@/lib/apply";
import type { Claim, ClaimSide, OfficerDetail, Reference } from "@/lib/officer";
import { useFetch } from "@/lib/use-fetch";

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[8rem_1fr] gap-2 py-1 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="break-words">{children}</dd>
    </div>
  );
}

/** One of the two applications, with what the DTO needs to judge who is genuine. */
function Side({
  side,
  heading,
  documentBase,
}: {
  side: ClaimSide;
  heading: string;
  documentBase: string;
}) {
  return (
    <div className="rounded-lg border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{heading}</h3>
        <Badge variant="outline">{side.status_label}</Badge>
      </div>
      <dl className="mt-1">
        <Fact label="Application">
          <span className="font-mono">{side.application_number}</span> · {side.district}
        </Fact>
        <Fact label="Submitted">{formatIst(side.submitted_at)}</Fact>
        <Fact label="Now with">{side.current_office}</Fact>
        <Fact label="Group leader">
          {side.leader_name}, {side.leader_mobile}
          {side.mobile_flagged && (
            <Badge variant="destructive" className="ml-2">
              Flagged mobile
            </Badge>
          )}
        </Fact>
        <Fact label="Owner">
          {side.owner_name}, {side.owner_mobile}
        </Fact>
        <Fact label="Vehicle">
          <span className="font-mono">{side.vehicle_reg_number}</span>
          {side.same_vehicle && " (same vehicle)"}
        </Fact>
        <Fact label="Driver">
          {side.driver_name}, {side.driver_mobile}
        </Fact>
        <Fact label="Licence">
          <span className="font-mono">{side.licence_number}</span>
          {side.same_driver && " (same driver)"}
        </Fact>
      </dl>
      <p className="text-muted-foreground mt-2 text-xs font-medium">Documents</p>
      <ul className="text-sm">
        {side.documents.map((d) => (
          <li key={d.id}>
            <a
              href={`${documentBase}/documents/${d.id}`}
              target="_blank"
              rel="noopener"
              className="underline underline-offset-4"
            >
              {d.label}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

type Open = { kind: "accept" | "reject"; item: Claim };

export default function ClaimsPage() {
  const { me } = useSession();
  const claims = useFetch<Claim[]>(me.role === "DTO" ? "/api/officer/claims" : null);
  const reference = useFetch<Reference>(me.role === "DTO" ? "/api/officer/reference" : null);
  const [open, setOpen] = useState<Open | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [remarks, setRemarks] = useState("");
  const [reason, setReason] = useState("");
  const [flag, setFlag] = useState(false);

  if (me.role !== "DTO") {
    return (
      <p role="alert" className="text-sm">
        Duplicate claims are resolved by the DTO. <Link href="/dashboard">Go to your page</Link>.
      </p>
    );
  }

  function start(next: Open) {
    setRemarks("");
    setReason("");
    setFlag(false);
    setOpen(next);
  }

  function finished(text: string) {
    setOpen(null);
    setNotice(text);
    claims.reload();
  }

  const approved = open?.item.blocking.find((side) => side.status === "APPROVED");

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <p className="text-sm">
          <Link href="/dashboard" className="underline underline-offset-4">
            Work queue
          </Link>
        </p>
        <h1 className="text-xl font-semibold tracking-tight">Duplicate claims</h1>
        <p className="text-muted-foreground text-sm">
          Each claim was raised by an applicant who was blocked because another application already
          uses the same vehicle or driver on that date. Check the registered owner in VAHAN, contact
          the owner, and compare the owner&rsquo;s self-certificate and RC of both. Then accept the
          claim or reject it.
        </p>
      </div>

      {notice && (
        <Alert>
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      )}
      {claims.error && (
        <p role="alert" className="text-destructive text-sm">
          {claims.error}
        </p>
      )}
      {claims.data?.length === 0 && (
        <p className="text-muted-foreground text-sm">No duplicate claim is waiting.</p>
      )}

      {(claims.data ?? []).map((item) => (
        <Card key={item.claim.id}>
          <CardHeader>
            <CardTitle>
              Claim <span className="font-mono">{item.claim.application_number}</span> · travel on{" "}
              {formatDay(item.claim.travel_date)}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-3 lg:grid-cols-2">
              <Side
                side={item.claim}
                heading="The claim (on hold)"
                documentBase={`/api/officer/claims/${item.claim.id}`}
              />
              {item.blocking.map((other) => (
                <Side
                  key={other.id}
                  side={other}
                  heading="The application that blocks it"
                  documentBase={`/api/officer/claims/${item.claim.id}/others/${other.id}`}
                />
              ))}
              {item.blocking.length === 0 && (
                <div className="text-muted-foreground rounded-lg border p-3 text-sm">
                  Nothing blocks this claim any more: the other application was rejected, cancelled
                  or changed. Accept the claim to take it up as a normal application.
                </div>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => start({ kind: "accept", item })}>Accept the claim</Button>
              <Button variant="destructive" onClick={() => start({ kind: "reject", item })}>
                Reject the claim
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}

      {open?.kind === "accept" && (
        <WorkDialog<OfficerDetail>
          title={`Accept claim ${open.item.claim.application_number}`}
          description={
            open.item.blocking.length > 0
              ? `The claim is genuine. Application ${open.item.blocking.map((side) => side.application_number).join(", ")} will be rejected with the reason “Not authorised by the vehicle owner or driver”, and the claim moves to your work queue. Both applicants are told by SMS.`
              : "The claim moves to your work queue as a normal application."
          }
          confirmLabel="Accept the claim"
          url={`/api/officer/claims/${open.item.claim.id}/accept`}
          build={() => ({ remarks, flag_mobiles: flag })}
          onClose={() => setOpen(null)}
          onDone={(result) =>
            finished(`Claim ${result.application_number} accepted. It is now in your work queue.`)
          }
        >
          {approved && (
            <Alert variant="destructive">
              <AlertTitle>Application {approved.application_number} is already approved</AlertTitle>
              <AlertDescription>
                Its permit has to be cancelled before this claim can be accepted.
              </AlertDescription>
            </Alert>
          )}
          <TextBox label="How you verified it (optional)" value={remarks} onChange={setRemarks} />
          {open.item.blocking.length > 0 && (
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={flag}
                onChange={(event) => setFlag(event.target.checked)}
              />
              The other application was fake or a prank: flag the mobile number that filed it.
            </label>
          )}
        </WorkDialog>
      )}

      {open?.kind === "reject" && (
        <WorkDialog<OfficerDetail>
          destructive
          title={`Reject claim ${open.item.claim.application_number}`}
          description="The claim is not genuine. It is closed, and the other application carries on. The claimant is told by SMS."
          confirmLabel="Reject the claim"
          url={`/api/officer/claims/${open.item.claim.id}/reject`}
          build={() => {
            if (!reason && !remarks.trim()) return "Choose a reason or write a remark.";
            return { reason_id: reason ? Number(reason) : null, remarks, flag_mobile: flag };
          }}
          onClose={() => setOpen(null)}
          onDone={(result) => finished(`Claim ${result.application_number} rejected.`)}
        >
          <div className="space-y-1.5">
            <Label htmlFor="claim-reason">Reason</Label>
            <NativeSelect
              id="claim-reason"
              className="w-full"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            >
              <NativeSelectOption value="">Choose a reason</NativeSelectOption>
              {(reference.data?.reject_reasons ?? []).map((option) => (
                <NativeSelectOption key={option.id} value={option.id}>
                  {option.name}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </div>
          <TextBox label="Remarks" value={remarks} onChange={setRemarks} />
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={flag}
              onChange={(event) => setFlag(event.target.checked)}
            />
            The claim was fake or a prank: flag the mobile number that filed it.
          </label>
        </WorkDialog>
      )}
    </div>
  );
}
