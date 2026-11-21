"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { ApplicationForm, FormLoading, FormMessage } from "@/components/apply/wizard";
import { api } from "@/lib/api";
import { EMPTY_FORM, type FormConfig } from "@/lib/apply";
import type { OfficerDetail } from "@/lib/officer";
import { useFetch } from "@/lib/use-fetch";

/**
 * An officer corrects an application the office holds, in the same six-step
 * form the applicant used. The API checks the login, the office and the
 * jurisdiction; this page only shows what the API allows.
 */
function CorrectContent() {
  const id = (useSearchParams().get("id") ?? "").replace(/\D/g, "");
  const config = useFetch<FormConfig>("/api/public/form-config");
  const detail = useFetch<OfficerDetail>(`/api/officer/applications/${id}`);
  const backHref = `/dashboard/application?id=${id}`;

  if (detail.error) {
    return (
      <FormMessage title="The application could not be opened">
        {detail.error}{" "}
        <Link href="/dashboard" className="underline">
          Go to the work queue
        </Link>
        .
      </FormMessage>
    );
  }
  if (config.error) {
    return <FormMessage title="The form could not be loaded">{config.error}</FormMessage>;
  }
  if (!config.data || !detail.data) return <FormLoading />;

  if (!detail.data.with_my_office) {
    return (
      <FormMessage title="This application is not pending with your office">
        Only the office that holds an application can correct it.{" "}
        <Link href={backHref} className="underline">
          Go to the application
        </Link>
        .
      </FormMessage>
    );
  }

  return (
    <ApplicationForm
      config={config.data}
      correction={{
        number: detail.data.application_number,
        initial: { ...EMPTY_FORM, ...detail.data.form },
        remarks: null,
        by: "officer",
        backHref,
        save: (payload, officer) =>
          api(`/api/officer/applications/${id}`, {
            method: "PUT",
            body: {
              application: payload,
              officer_name: officer.name,
              officer_designation: officer.designation,
            },
          }),
      }}
    />
  );
}

export default function CorrectApplicationPage() {
  return (
    <Suspense fallback={<FormLoading />}>
      <CorrectContent />
    </Suspense>
  );
}
