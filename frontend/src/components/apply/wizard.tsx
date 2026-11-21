"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FormProvider, useForm, useFormContext, useWatch } from "react-hook-form";

import {
  controlClass,
  ErrorText,
  Help,
  Notice,
  OutlineButton,
  PrimaryButton,
  Section,
  Tick,
} from "@/components/apply/fields";
import {
  StepDestination,
  StepDriver,
  StepLeaderAndJourney,
  StepPassengers,
  StepVehicle,
} from "@/components/apply/steps";
import { OtpGate, type OtpSent } from "@/components/public/otp-gate";
import { PublicPage } from "@/components/public/shell";
import { api, ApiError, errorMessage } from "@/lib/api";
import {
  buildSchema,
  clearSaved,
  EMPTY_FORM,
  firstInvalidStep,
  KIT_ITEMS,
  loadSaved,
  saveLocally,
  STEP_TITLES,
  stepOfField,
  stepPaths,
  toPayload,
  UNDERTAKING_POINTS,
  type FormConfig,
  type FormValues,
} from "@/lib/apply";
import { loadOfficer, saveOfficer, type Officer } from "@/lib/officer";
import { useFetch } from "@/lib/use-fetch";

type Duplicate = { vehicle: boolean; driver: boolean; message: string };
type Submitted = { application_number: string; status: string; message: string };

/** A returned application being corrected, instead of a new one. */
export type Correction = {
  number: string;
  initial: FormValues;
  /** The officer's remarks, shown at the top of every step. */
  remarks: string | null;
  /**
   * Who is correcting. The applicant corrects a returned application and
   * cannot change the starting district. An officer corrects one the office
   * holds, and can.
   */
  by: "applicant" | "officer";
  /** Sends the corrected form. Returns where the application is now. */
  save: (
    payload: ReturnType<typeof toPayload>,
    officer: Officer,
  ) => Promise<{ status: string; status_label: string; current_office: string }>;
  /** Where "Back to the application" leads after saving. */
  backHref: string;
};

// ------------------------------------------------------------------- frame

function Progress({ step }: { step: number }) {
  return (
    <div className="border-portal-line border-b bg-white px-5 pt-4 pb-3">
      <div className="mx-auto flex w-full max-w-xl flex-col gap-2">
        <div className="text-portal-muted text-[13px] font-semibold">Step {step + 1} of 6</div>
        <h1 className="text-[22px] leading-tight font-bold">{STEP_TITLES[step]}</h1>
        <div aria-hidden="true" className="grid grid-cols-6 gap-1">
          {STEP_TITLES.map((title, index) => (
            <div
              key={title}
              className={`h-1.5 rounded-full ${index <= step ? "bg-portal-blue" : "bg-portal-line"}`}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------- step 6

function UndertakingSections() {
  return (
    <>
      <Section title="Emergency kit in the vehicle">
        <Help>Tick each item that will be carried.</Help>
        {KIT_ITEMS.map((item) => (
          <Tick key={item.name} name={item.name} label={item.label} />
        ))}
      </Section>

      <Section title="Emergency contacts">
        <Tick
          name="emergency_contacts_saved"
          label="I will save 112, 108, the District Police Control Room, the nearest police station, hospital and fire service numbers before departure."
        />
      </Section>

      <Section title="Undertaking by the group leader">
        <ul className="flex list-disc flex-col gap-2 pl-5 text-[15px] leading-snug">
          {UNDERTAKING_POINTS.map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>
        <a
          href="/sop.pdf"
          target="_blank"
          rel="noopener"
          className="text-portal-blue text-[15px] font-semibold underline"
        >
          Read the Picnic Journeys SOP (PDF)
        </a>
        <Tick name="undertaking_accepted" label="I have read and accept this undertaking." />
      </Section>
    </>
  );
}

type StepSixProps = {
  /** The first step that breaks a rule, or null when the form is in order. */
  findInvalidStep: () => number | null;
  onInvalid: (step: number) => void;
  onSubmitted: (result: Submitted) => void;
};

/** Checks the whole form in the browser and shows the server's field messages. */
function useFormChecks({ findInvalidStep, onInvalid }: StepSixProps) {
  const { trigger, setError } = useFormContext<FormValues>();
  const [problem, setProblem] = useState<string | null>(null);

  /** True when every rule passes in the browser. Otherwise opens the first bad step. */
  const passesLocally = useCallback(async () => {
    setProblem(null);
    if (await trigger()) return true;
    const bad = findInvalidStep();
    if (bad !== null && bad < 5) onInvalid(bad);
    else setProblem("Please tick every required item above.");
    return false;
  }, [trigger, findInvalidStep, onInvalid]);

  /** Shows the server's field messages. False if the error was not about fields. */
  const showServerErrors = useCallback(
    (error: unknown) => {
      if (!(error instanceof ApiError) || Object.keys(error.fieldErrors).length === 0) return false;
      const paths = Object.keys(error.fieldErrors);
      for (const path of paths) {
        setError(path as keyof FormValues, { type: "server", message: error.fieldErrors[path] });
      }
      const first = Math.min(...paths.map(stepOfField));
      if (first < 5) onInvalid(first);
      else setProblem("Please correct the highlighted items above.");
      return true;
    },
    [setError, onInvalid],
  );

  return { problem, setProblem, passesLocally, showServerErrors };
}

function StepUndertaking(props: StepSixProps & { config: FormConfig }) {
  const { config, onSubmitted } = props;
  const { getValues } = useFormContext<FormValues>();
  const { problem, setProblem, passesLocally, showServerErrors } = useFormChecks(props);

  const [duplicate, setDuplicate] = useState<Duplicate | null>(null);
  const [raiseClaim, setRaiseClaim] = useState(false);
  // The gate is rebuilt when a claim is raised, so it starts again from the captcha.
  const mobile = getValues("leader_mobile");

  async function send(
    captcha: { captcha_id: string | null | undefined; captcha_answer: string },
    claim: boolean,
  ): Promise<OtpSent | null> {
    // 1. The rules, in the browser and then on the server.
    if (!(await passesLocally())) return null;
    const values = getValues();
    try {
      const checked = await api<{ duplicate: Duplicate | null }>("/api/public/applications/check", {
        method: "POST",
        body: toPayload(values),
      });
      // 2. The duplicate check: the applicant corrects the form or raises a claim.
      if (checked.duplicate && !claim) {
        setDuplicate(checked.duplicate);
        return null;
      }
      setDuplicate(null);
      setRaiseClaim(Boolean(checked.duplicate) && claim);
    } catch (error) {
      if (showServerErrors(error)) return null;
      throw error;
    }
    // 3. The OTP.
    return api<OtpSent>("/api/public/applications/otp", {
      method: "POST",
      body: { mobile: values.leader_mobile, ...captcha },
    });
  }

  async function confirm(otpId: string, code: string) {
    try {
      const result = await api<Submitted>("/api/public/applications", {
        method: "POST",
        body: {
          application: toPayload(getValues()),
          otp_id: otpId,
          otp_code: code,
          raise_claim: raiseClaim,
        },
      });
      onSubmitted(result);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        // Someone else applied for the same vehicle or driver in the meantime.
        setDuplicate({ vehicle: true, driver: true, message: error.message });
        return;
      }
      if (showServerErrors(error)) return;
      throw error;
    }
  }

  return (
    <>
      <UndertakingSections />

      {duplicate && (
        <Notice tone="warn" title={duplicate.message}>
          <p>
            A vehicle or a driver cannot be on two picnic trips on the same day. If the details are
            wrong, go back and correct them.
          </p>
          <p className="mt-2">
            If this is your own vehicle or driver and someone else has used it without your consent,
            you can raise a claim. Your application will be put on hold and the DTO will verify
            which one is genuine.
          </p>
          <div className="mt-3 flex flex-col gap-2">
            <OutlineButton
              onClick={() => {
                setRaiseClaim(true);
                setDuplicate(null);
              }}
            >
              This is my vehicle or driver: raise a claim
            </OutlineButton>
          </div>
        </Notice>
      )}

      <Section title="Confirm by OTP">
        {raiseClaim && (
          <Notice tone="info">
            You are raising a claim. After submission the application will be on hold until the DTO
            decides. Send the OTP to continue.
          </Notice>
        )}
        <ErrorText>{problem}</ErrorText>
        <OtpGate
          intro={
            <>
              An OTP will be sent to the group leader&rsquo;s mobile number {mobile}. Entering it
              confirms the undertaking.
            </>
          }
          mobile={mobile}
          otpLength={config.otp_length}
          confirmLabel="Submit application"
          confirmingLabel="Submitting…"
          send={(captcha) => {
            setProblem(null);
            return send(captcha, raiseClaim);
          }}
          confirm={confirm}
        />
      </Section>

      <Help>
        Submitting this application is not permission to travel. You will get an SMS at each stage.
        After final approval, download the permit with its QR code from this portal and print it.
      </Help>
    </>
  );
}

/**
 * Step 6 of a correction. The person is already known (the group leader by
 * OTP, or a logged-in officer), so there is no OTP: it only saves.
 */
function StepResubmit(props: StepSixProps & { correction: Correction }) {
  const { correction, onSubmitted } = props;
  const byOfficer = correction.by === "officer";
  const { getValues } = useFormContext<FormValues>();
  const { problem, setProblem, passesLocally, showServerErrors } = useFormChecks(props);
  const [busy, setBusy] = useState(false);
  const [officer, setOfficer] = useState(loadOfficer);

  async function save() {
    if (!(await passesLocally())) return;
    if (byOfficer && (!officer.name.trim() || !officer.designation.trim())) {
      setProblem("Enter your name and designation.");
      return;
    }
    setBusy(true);
    try {
      if (byOfficer) saveOfficer(officer);
      const result = await correction.save(toPayload(getValues()), officer);
      onSubmitted({
        application_number: correction.number,
        status: result.status,
        message: byOfficer
          ? `The corrections are saved and the applicant is told by SMS. The application is now: ${result.status_label} (${result.current_office}).`
          : `Your corrected application is resubmitted. It is now: ${result.status_label} (${result.current_office}).`,
      });
    } catch (error) {
      if (showServerErrors(error)) return;
      if (error instanceof ApiError && error.status === 401) {
        setProblem(
          byOfficer
            ? "Your login has ended. Log in again in another tab, then save. Your changes on this screen are kept while this page stays open."
            : "Your session has ended. Open the status page, confirm the OTP again, and resubmit. Your changes on this screen are kept while this page stays open.",
        );
      } else {
        setProblem(errorMessage(error));
      }
    } finally {
      setBusy(false);
    }
  }

  if (byOfficer) {
    return (
      <>
        <UndertakingSections />
        <Section title="Save corrections">
          <Help>
            Every change is logged with your name, the old value and the new value, and the
            applicant is told by SMS what was changed. If you changed the district, the vehicle or
            the driver, the application goes to the DTO.
          </Help>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="officer-name" className="text-sm font-semibold">
              Your name
            </label>
            <input
              id="officer-name"
              className={controlClass}
              maxLength={100}
              value={officer.name}
              onChange={(event) => setOfficer({ ...officer, name: event.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="officer-designation" className="text-sm font-semibold">
              Your designation
            </label>
            <input
              id="officer-designation"
              className={controlClass}
              maxLength={100}
              value={officer.designation}
              onChange={(event) => setOfficer({ ...officer, designation: event.target.value })}
            />
          </div>
          <ErrorText>{problem}</ErrorText>
          <PrimaryButton disabled={busy} onClick={() => void save()}>
            {busy ? "Saving…" : "Save corrections"}
          </PrimaryButton>
        </Section>
      </>
    );
  }

  return (
    <>
      <UndertakingSections />
      <Section title="Resubmit">
        <Help>
          Your corrected application goes back to the office that returned it. If you changed the
          vehicle or the driver, it goes to the DTO to be checked again.
        </Help>
        <ErrorText>{problem}</ErrorText>
        <PrimaryButton disabled={busy} onClick={() => void save()}>
          {busy ? "Resubmitting…" : "Resubmit application"}
        </PrimaryButton>
      </Section>
      <Help>Resubmitting is not permission to travel. You will get an SMS at each stage.</Help>
    </>
  );
}

// --------------------------------------------------------------- confirmation

function Confirmation({
  result,
  correction,
  onNew,
}: {
  result: Submitted;
  correction?: Correction;
  onNew: () => void;
}) {
  const onHold = result.status === "ON_HOLD_DUPLICATE_CLAIM";
  const corrected = Boolean(correction);
  const title =
    correction?.by === "officer"
      ? "Corrections saved"
      : corrected
        ? "Application resubmitted"
        : onHold
          ? "Application received and put on hold"
          : "Application submitted";
  return (
    <PublicPage>
      <main className="mx-auto flex w-full max-w-xl flex-col gap-4 px-5 py-6">
        <section className="border-portal-line flex flex-col gap-3 rounded-lg border bg-white p-5">
          <h1 className="text-[22px] leading-tight font-bold">{title}</h1>
          <div>
            <div className="text-portal-muted text-[13px] font-semibold">Application number</div>
            <div className="text-[28px] font-bold tracking-wide select-all">
              {result.application_number}
            </div>
          </div>
          <p className="text-[15px] leading-snug">{result.message}</p>
          {correction?.by !== "officer" && (
            <>
              <Notice tone="warn" title="This is not permission to travel">
                Do not start the journey until final approval is given and the QR code is displayed
                on the windscreen.
              </Notice>
              <Help>
                Note the application number. An SMS with it has been sent to the group
                leader&rsquo;s mobile number, and you will get an SMS at each stage.
              </Help>
            </>
          )}
        </section>
        <div className="flex flex-col gap-3 sm:flex-row">
          {correction ? (
            <Link
              href={correction.backHref}
              className="bg-portal-blue flex h-12 grow items-center justify-center rounded-md px-4 text-base font-semibold text-white"
            >
              Back to the application
            </Link>
          ) : (
            <>
              <OutlineButton className="grow" onClick={onNew}>
                Apply for another vehicle
              </OutlineButton>
              <Link
                href={`/status?q=${result.application_number}`}
                className="bg-portal-blue flex h-12 grow items-center justify-center rounded-md px-4 text-base font-semibold text-white"
              >
                Check status
              </Link>
            </>
          )}
        </div>
      </main>
    </PublicPage>
  );
}

// ------------------------------------------------------------------ the form

export function ApplicationForm({
  config,
  correction,
}: {
  config: FormConfig;
  correction?: Correction;
}) {
  const schema = useMemo(() => buildSchema(config), [config]);
  // A new application: bring back what was typed before a refresh. This
  // component is shown only in the browser, so storage is there.
  // A correction starts from the application itself and is not stored.
  const [saved] = useState(() => (correction ? null : loadSaved()));
  const methods = useForm<FormValues>({
    resolver: zodResolver(schema),
    mode: "onTouched",
    defaultValues: correction?.initial ?? saved?.values ?? EMPTY_FORM,
  });
  const { reset, trigger, control, getValues } = methods;

  const [step, setStep] = useState(saved?.step ?? 0);
  const [result, setResult] = useState<Submitted | null>(null);
  // True after "Save and continue" was refused, so the button never fails silently.
  const [stuck, setStuck] = useState(false);
  const top = useRef<HTMLDivElement>(null);
  const isCorrection = Boolean(correction);

  // Keep the entries of a new application on this device as they change.
  const values = useWatch({ control });
  useEffect(() => {
    if (!result && !isCorrection) saveLocally({ ...EMPTY_FORM, ...values } as FormValues, step);
  }, [values, step, result, isCorrection]);

  const go = useCallback((next: number) => {
    setStep(next);
    setStuck(false);
    top.current?.scrollIntoView({ block: "start" });
  }, []);

  async function next() {
    // Only this step's own fields are checked, so a later step cannot block it.
    const paths = stepPaths(step, config) as Parameters<typeof trigger>[0];
    if (await trigger(paths)) {
      go(step + 1);
    } else {
      setStuck(true);
    }
  }

  function startAgain() {
    clearSaved();
    reset(EMPTY_FORM);
    setResult(null);
    go(0);
  }

  if (result) {
    return <Confirmation result={result} correction={correction} onNew={startAgain} />;
  }

  const stepSix: StepSixProps = {
    findInvalidStep: () => firstInvalidStep(schema, getValues()),
    onInvalid: go,
    onSubmitted: (submitted) => {
      if (!isCorrection) clearSaved();
      setResult(submitted);
      top.current?.scrollIntoView({ block: "start" });
    },
  };

  return (
    <PublicPage>
      <div ref={top} />
      <Progress step={step} />
      <FormProvider {...methods}>
        <form
          noValidate
          onSubmit={(event) => event.preventDefault()}
          className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-4 px-5 py-4"
        >
          {correction && (
            <Notice
              tone="warn"
              title={
                correction.by === "officer"
                  ? `Correcting application ${correction.number}`
                  : `Correcting application ${correction.number}, returned for correction`
              }
            >
              {correction.remarks && <p>Remarks from the office: {correction.remarks}</p>}
              <p className={correction.remarks ? "mt-1" : ""}>
                Change what is needed in any step, then{" "}
                {correction.by === "officer" ? "save the corrections" : "resubmit"} in Step 6.
              </p>
            </Notice>
          )}

          {step === 0 && <StepLeaderAndJourney config={config} locked={correction?.by} />}
          {step === 1 && <StepDestination />}
          {step === 2 && <StepVehicle config={config} />}
          {step === 3 && <StepDriver config={config} />}
          {step === 4 && <StepPassengers config={config} onEditLeader={() => go(0)} />}
          {step === 5 &&
            (correction ? (
              <StepResubmit correction={correction} {...stepSix} />
            ) : (
              <StepUndertaking config={config} {...stepSix} />
            ))}

          {step === 0 && !isCorrection && (
            <button
              type="button"
              className="text-portal-muted self-start text-[13px] underline"
              onClick={() => {
                if (window.confirm("Clear everything you have entered and start again?")) {
                  startAgain();
                }
              }}
            >
              Clear the form and start again
            </button>
          )}
        </form>
      </FormProvider>

      <div className="border-portal-line sticky bottom-0 border-t bg-white px-5 py-3">
        {stuck && (
          <p
            role="alert"
            className="text-portal-error mx-auto mb-2 w-full max-w-xl text-[13px] font-medium"
          >
            Please correct the items marked in red above, then continue.
          </p>
        )}
        <div className="mx-auto flex w-full max-w-xl gap-3">
          {step > 0 && (
            <OutlineButton className="w-24" onClick={() => go(step - 1)}>
              Back
            </OutlineButton>
          )}
          {step < 5 && (
            <PrimaryButton className="grow" onClick={() => void next()}>
              Save and continue
            </PrimaryButton>
          )}
        </div>
      </div>
    </PublicPage>
  );
}

export function FormMessage({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <PublicPage>
      <main className="mx-auto w-full max-w-xl px-5 py-6">
        <Notice tone="error" title={title}>
          {children}
        </Notice>
      </main>
    </PublicPage>
  );
}

export function FormLoading() {
  return (
    <PublicPage>
      <p className="text-portal-muted mx-auto w-full max-w-xl px-5 py-6 text-sm">Loading…</p>
    </PublicPage>
  );
}

export function ApplyWizard() {
  const config = useFetch<FormConfig>("/api/public/form-config");

  if (config.error) {
    return (
      <FormMessage title="The form could not be loaded">
        {config.error} Please check your connection and reload the page.
      </FormMessage>
    );
  }
  if (!config.data) return <FormLoading />;
  return <ApplicationForm config={config.data} />;
}
