"use client";

import Link from "next/link";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

import { ApplicationForm, FormLoading, FormMessage } from "@/components/apply/wizard";
import { api } from "@/lib/api";
import { EMPTY_FORM, type FormConfig } from "@/lib/apply";
import type { ApplicationDetail } from "@/lib/status";
import { useFetch } from "@/lib/use-fetch";

function CorrectContent() {
  const number = (useSearchParams().get("n") ?? "").replace(/\D/g, "");
  const config = useFetch<FormConfig>("/api/public/form-config");
  const detail = useFetch<ApplicationDetail>(`/api/public/my/applications/${number}`);

  const back = (
    <Link href={`/status/application?n=${number}`} className="underline">
      Go to the application
    </Link>
  );

  if (detail.error) {
    return (
      <FormMessage title="Please confirm the OTP first">
        The application can be corrected only by the group leader, after an OTP. {back}.
      </FormMessage>
    );
  }
  if (config.error) {
    return <FormMessage title="The form could not be loaded">{config.error}</FormMessage>;
  }
  if (!config.data || !detail.data) return <FormLoading />;

  if (!detail.data.can_correct) {
    return (
      <FormMessage title="This application cannot be corrected now">
        Only an application returned for correction can be changed. Its status is{" "}
        {detail.data.status_label}. {back}.
      </FormMessage>
    );
  }

  return (
    <ApplicationForm
      config={config.data}
      correction={{
        number,
        initial: { ...EMPTY_FORM, ...detail.data.form },
        remarks: detail.data.remarks,
        by: "applicant",
        backHref: `/status/application?n=${number}`,
        save: (payload) =>
          api(`/api/public/my/applications/${number}`, { method: "PUT", body: payload }),
      }}
    />
  );
}

/** The six-step form, filled with a returned application, for correction and resubmission. */
export default function CorrectPage() {
  return (
    <Suspense fallback={<FormLoading />}>
      <CorrectContent />
    </Suspense>
  );
}
