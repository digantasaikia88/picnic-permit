"use client";

import { RefreshCwIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { controlClass, ErrorText, Help, Notice, PrimaryButton } from "@/components/apply/fields";
import { api, errorMessage, type Captcha } from "@/lib/api";

export type OtpSent = {
  otp_id: string;
  resend_after_seconds: number;
  /** Development only: the code, because no SMS is sent. */
  dev_otp: string | null;
  /** The number the OTP went to, masked, when the visitor did not type it. */
  sent_to?: string | null;
};

type CaptchaAnswer = { captcha_id: string | null | undefined; captcha_answer: string };

function Countdown({ until, onDone }: { until: number; onDone: () => void }) {
  const [left, setLeft] = useState(() => Math.max(0, Math.ceil((until - Date.now()) / 1000)));
  useEffect(() => {
    const timer = setInterval(() => {
      const seconds = Math.max(0, Math.ceil((until - Date.now()) / 1000));
      setLeft(seconds);
      if (seconds === 0) {
        clearInterval(timer);
        onDone();
      }
    }, 500);
    return () => clearInterval(timer);
  }, [until, onDone]);
  return <>{left}</>;
}

/**
 * Captcha, then an OTP by SMS, then the code.
 *
 * `send` asks the server for the OTP. It may return null to stop quietly (the
 * caller has shown its own message, for example a form error). `confirm`
 * checks the code; an error it throws is shown under the field.
 */
export function OtpGate({
  intro,
  mobile,
  otpLength = 6,
  sendLabel = "Send OTP",
  confirmLabel,
  confirmingLabel = "Checking…",
  send,
  confirm,
}: {
  intro: React.ReactNode;
  /** The number the OTP goes to, when it is known on this screen. */
  mobile?: string;
  otpLength?: number;
  sendLabel?: string;
  confirmLabel: string;
  confirmingLabel?: string;
  send: (captcha: CaptchaAnswer) => Promise<OtpSent | null>;
  confirm: (otpId: string, code: string) => Promise<void>;
}) {
  const [captcha, setCaptcha] = useState<Captcha | null>(null);
  const [answer, setAnswer] = useState("");
  const [sent, setSent] = useState<OtpSent | null>(null);
  const [code, setCode] = useState("");
  const [resendAt, setResendAt] = useState(0);
  const [canResend, setCanResend] = useState(true);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadCaptcha = useCallback(async () => {
    setAnswer("");
    try {
      setCaptcha(await api<Captcha>("/api/auth/captcha"));
    } catch (error) {
      setProblem(errorMessage(error));
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    api<Captcha>("/api/auth/captcha")
      .then((value) => {
        if (!cancelled) setCaptcha(value);
      })
      .catch((error: unknown) => {
        if (!cancelled) setProblem(errorMessage(error));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSend() {
    setProblem(null);
    if (captcha?.enabled && !answer.trim()) {
      setProblem("Type the text shown in the picture, then send the OTP.");
      return;
    }
    setBusy(true);
    try {
      const result = await send({ captcha_id: captcha?.captcha_id, captcha_answer: answer });
      if (result) {
        setSent(result);
        setCode("");
        setCanResend(false);
        setResendAt(Date.now() + result.resend_after_seconds * 1000);
      }
      // A captcha works once, whatever the outcome.
      await loadCaptcha();
    } catch (error) {
      setProblem(errorMessage(error));
      await loadCaptcha();
    } finally {
      setBusy(false);
    }
  }

  async function onConfirm() {
    if (!sent) return;
    setProblem(null);
    setBusy(true);
    try {
      await confirm(sent.otp_id, code.trim());
    } catch (error) {
      setProblem(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  const markResendReady = useCallback(() => setCanResend(true), []);
  const target = mobile ?? sent?.sent_to ?? "the mobile number";

  if (!sent) {
    return (
      <>
        <Help>{intro}</Help>
        {captcha?.enabled && (
          <div className="flex flex-col gap-1.5">
            <label htmlFor="otp-captcha" className="text-sm font-semibold">
              Type the text shown in the picture
            </label>
            <div className="flex items-center gap-2">
              {captcha.image && (
                // eslint-disable-next-line @next/next/no-img-element -- a data URL, not a file
                <img
                  src={captcha.image}
                  alt="Captcha text"
                  width={200}
                  height={70}
                  className="border-portal-line h-[52px] w-[150px] rounded-md border"
                />
              )}
              <button
                type="button"
                onClick={() => void loadCaptcha()}
                aria-label="Show a different picture"
                className="border-portal-field text-portal-blue flex size-11 items-center justify-center rounded-md border bg-white"
              >
                <RefreshCwIcon className="size-4" />
              </button>
            </div>
            <input
              id="otp-captcha"
              className={controlClass}
              autoComplete="off"
              autoCapitalize="characters"
              spellCheck={false}
              value={answer}
              onChange={(event) => setAnswer(event.target.value)}
            />
          </div>
        )}
        <ErrorText>{problem}</ErrorText>
        <PrimaryButton disabled={busy || !captcha} onClick={() => void onSend()}>
          {busy ? "Checking…" : sendLabel}
        </PrimaryButton>
      </>
    );
  }

  return (
    <>
      <div className="flex flex-col gap-1.5">
        <label htmlFor="otp-code" className="text-sm font-semibold">
          OTP sent to {target}
        </label>
        <input
          id="otp-code"
          className={`${controlClass} tracking-[0.3em]`}
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={otpLength}
          value={code}
          onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
        />
        {sent.dev_otp && (
          <Notice tone="warn" title="Development only">
            No SMS is sent on a development computer. The OTP is{" "}
            <strong className="tracking-widest">{sent.dev_otp}</strong>. This box never appears on
            the live site.
          </Notice>
        )}
      </div>
      <ErrorText>{problem}</ErrorText>
      <PrimaryButton disabled={busy || code.length !== otpLength} onClick={() => void onConfirm()}>
        {busy ? confirmingLabel : confirmLabel}
      </PrimaryButton>
      <button
        type="button"
        disabled={!canResend || busy}
        className="text-portal-blue disabled:text-portal-muted text-sm font-semibold underline disabled:no-underline"
        onClick={() => {
          setSent(null);
          setProblem(null);
        }}
      >
        {canResend ? (
          "Did not get it? Send a new OTP"
        ) : (
          <>
            You can ask for a new OTP in <Countdown until={resendAt} onDone={markResendReady} />{" "}
            seconds
          </>
        )}
      </button>
    </>
  );
}
