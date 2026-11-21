"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { controlClass, ErrorText, Help, Notice, PrimaryButton } from "@/components/apply/fields";
import { formatDay } from "@/lib/apply";
import { statusTone, type PublicStatus } from "@/lib/status";
import { cn } from "@/lib/utils";

const TONE_CLASS = {
  info: "bg-portal-tint text-portal-navy border-portal-blue",
  warn: "bg-portal-warn-bg text-portal-warn-text border-portal-warn-line",
  ok: "bg-emerald-50 text-portal-ok border-portal-ok",
  closed: "bg-portal-bg text-portal-muted border-portal-field",
};

export function StatusLabel({ status, label }: { status: string; label: string }) {
  return (
    <span
      className={cn(
        "inline-flex w-fit rounded-full border px-3 py-1 text-sm font-semibold",
        TONE_CLASS[statusTone(status)],
      )}
    >
      {label}
    </span>
  );
}

export function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-2">
      <dt className="text-portal-muted shrink-0 text-[13px]">{label}</dt>
      <dd className="text-right text-[15px] font-medium break-words">{children}</dd>
    </div>
  );
}

/** What anyone may see of an application. */
export function StatusCard({ item, children }: { item: PublicStatus; children?: React.ReactNode }) {
  return (
    <section className="border-portal-line flex flex-col gap-3 rounded-lg border bg-white p-4">
      <div className="flex flex-col gap-2">
        <div>
          <div className="text-portal-muted text-[13px] font-semibold">Application number</div>
          <div className="text-xl font-bold tracking-wide">{item.application_number}</div>
        </div>
        <StatusLabel status={item.status} label={item.status_label} />
      </div>
      <dl className="divide-portal-line divide-y">
        <Fact label="Date of travel">{formatDay(item.travel_date)}</Fact>
        <Fact label="Now with">{item.current_office}</Fact>
      </dl>
      {item.remarks && (
        <Notice
          tone="warn"
          title={item.status === "REJECTED" ? "Reason for rejection" : "Remarks from the office"}
        >
          {item.remarks}
        </Notice>
      )}
      {children}
    </section>
  );
}

/** The search box of the landing page and the status page. */
export function StatusSearchBox({ initial = "" }: { initial?: string }) {
  const router = useRouter();
  const [query, setQuery] = useState(initial);
  const [problem, setProblem] = useState<string | null>(null);

  function search() {
    const digits = query.replace(/\D/g, "");
    if (digits.length !== 11 && !/^[6-9][0-9]{9}$/.test(digits)) {
      setProblem("Enter the 11-digit application number, or the 10-digit mobile number.");
      return;
    }
    setProblem(null);
    router.push(`/status?q=${digits}`);
  }

  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        search();
      }}
    >
      <label htmlFor="status-query" className="text-sm font-semibold">
        Application number or mobile number
      </label>
      <input
        id="status-query"
        className={controlClass}
        inputMode="numeric"
        autoComplete="off"
        maxLength={20}
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      <ErrorText>{problem}</ErrorText>
      <PrimaryButton type="submit">Check status</PrimaryButton>
      <Help>A search by mobile number needs an OTP sent to that number.</Help>
    </form>
  );
}
