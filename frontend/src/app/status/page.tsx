"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Help, Notice, OutlineButton, Section } from "@/components/apply/fields";
import { OtpGate, type OtpSent } from "@/components/public/otp-gate";
import { Column, PublicPage } from "@/components/public/shell";
import { StatusCard, StatusSearchBox } from "@/components/public/status-parts";
import { api } from "@/lib/api";
import { maskMobile, type ApplicantMe, type PublicStatus } from "@/lib/status";
import { useFetch } from "@/lib/use-fetch";

const MOBILE = /^[6-9][0-9]{9}$/;

function actionLabel(status: string): string {
  if (status === "RETURNED_TO_APPLICANT") return "Correct and resubmit";
  if (status === "PENDING_DTO") return "View details or upload the inspection certificate";
  return "View full details";
}

function StatusContent() {
  const router = useRouter();
  const query = (useSearchParams().get("q") ?? "").replace(/\D/g, "");
  const isMobile = MOBILE.test(query) && query.length === 10;
  const isNumber = query.length === 11;

  // The confirmed mobile number of this browser, if an OTP was entered in the last while.
  const session = useFetch<ApplicantMe>("/api/public/my/session");
  const signedIn = session.data && !session.error ? session.data : null;
  const mine = useFetch<PublicStatus[]>(signedIn ? "/api/public/my/applications" : null);
  const found = useFetch<PublicStatus>(isNumber ? `/api/public/status/${query}` : null);
  const [signedOut, setSignedOut] = useState(false);

  const showMine = signedIn && !signedOut && (!query || (isMobile && query === signedIn.mobile));
  const needsMobileOtp = isMobile && !showMine;

  async function signOut() {
    await api("/api/public/status-access/logout", { method: "POST" });
    setSignedOut(true);
    router.replace("/status");
  }

  return (
    <Column>
      <h1 className="text-[22px] leading-tight font-bold">Application status</h1>

      <Section title="Search">
        <StatusSearchBox key={query} initial={query} />
      </Section>

      {/* Search by application number: open to anyone. */}
      {isNumber && found.error && (
        <Notice tone="error" title="Not found">
          {found.error}
        </Notice>
      )}
      {isNumber && found.data && !found.error && (
        <StatusCard item={found.data}>
          <Link
            href={`/status/application?n=${found.data.application_number}`}
            className="border-portal-blue text-portal-blue hover:bg-portal-tint flex min-h-12 items-center justify-center rounded-md border bg-white px-4 py-2 text-center text-base font-semibold"
          >
            {actionLabel(found.data.status)}
          </Link>
          <Help>
            Full details need an OTP sent to the group leader&rsquo;s mobile number, so that only
            the group leader can see or change the application.
          </Help>
        </StatusCard>
      )}

      {/* Search by mobile number: needs an OTP to that number. */}
      {needsMobileOtp && (
        <Section title={`Applications of ${maskMobile(query)}`}>
          <OtpGate
            key={query}
            intro={
              <>
                To show the applications of this mobile number, we send an OTP to it. If the number
                has no applications, no OTP is sent.
              </>
            }
            mobile={maskMobile(query)}
            confirmLabel="Show my applications"
            send={(captcha) =>
              api<OtpSent>("/api/public/status-access/otp", {
                method: "POST",
                body: { mobile: query, ...captcha },
              })
            }
            confirm={async (otpId, code) => {
              await api("/api/public/status-access/session", {
                method: "POST",
                body: { otp_id: otpId, otp_code: code },
              });
              setSignedOut(false);
              session.reload();
            }}
          />
        </Section>
      )}

      {showMine && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-[17px] font-bold">Applications of {maskMobile(signedIn.mobile)}</h2>
            <OutlineButton className="min-h-10 px-3 text-sm" onClick={() => void signOut()}>
              Sign out
            </OutlineButton>
          </div>
          {mine.data?.length === 0 && (
            <Notice tone="info">No applications were found for this mobile number.</Notice>
          )}
          {(mine.data ?? []).map((item) => (
            <StatusCard key={item.application_number} item={item}>
              <Link
                href={`/status/application?n=${item.application_number}`}
                className="border-portal-blue text-portal-blue hover:bg-portal-tint flex min-h-12 items-center justify-center rounded-md border bg-white px-4 py-2 text-center text-base font-semibold"
              >
                {actionLabel(item.status)}
              </Link>
            </StatusCard>
          ))}
        </>
      )}

      <Help>
        The status shown here is not permission to travel. A journey may start only after final
        approval, with the QR code displayed on the windscreen.
      </Help>
    </Column>
  );
}

export default function StatusPage() {
  return (
    <PublicPage footer>
      {/* The search text is read from the address, which needs a Suspense boundary. */}
      <Suspense fallback={<Column>Loading…</Column>}>
        <StatusContent />
      </Suspense>
    </PublicPage>
  );
}
