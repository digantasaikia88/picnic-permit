"use client";

import { useRef, useState } from "react";
import { useFormContext } from "react-hook-form";

import { ErrorText, Help, useFieldError } from "@/components/apply/fields";
import { api, errorMessage } from "@/lib/api";
import {
  compressPhoto,
  formatSize,
  type DocType,
  type FormConfig,
  type FormValues,
  type Uploaded,
} from "@/lib/apply";

type UploadAnswer = { token: string; original_name: string; size_bytes: number };

/** A document already on a returned application, not a fresh upload. It can be replaced, not removed. */
const isExisting = (token: string) => token.startsWith("existing:");

/** One document: its name, an Upload button, and the chosen file once uploaded. */
export function UploadRow({
  rule,
  maxMb,
  help,
  children,
}: {
  rule: FormConfig["documents"][number];
  maxMb: number;
  help?: string;
  /** Extra content under the name, such as a link to a blank form. */
  children?: React.ReactNode;
}) {
  const { watch, setValue, clearErrors } = useFormContext<FormValues>();
  const path = `documents.${rule.doc_type}` as `documents.${DocType}`;
  const current = watch(path) as Uploaded | null | undefined;
  const fieldError = useFieldError(path);
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function choose(file: File) {
    setProblem(null);
    setBusy(true);
    try {
      const prepared = await compressPhoto(file);
      if (prepared.size > maxMb * 1024 * 1024) {
        setProblem(`This file is larger than ${maxMb} MB.`);
        return;
      }
      const form = new FormData();
      form.append("doc_type", rule.doc_type);
      form.append("file", prepared, prepared.name);
      const saved = await api<UploadAnswer>("/api/public/uploads", { method: "POST", form });

      // Replacing a file: the earlier one is no longer needed on the server.
      if (current && !isExisting(current.token))
        void api(`/api/public/uploads/${current.token}`, { method: "DELETE" }).catch(() => {});

      setValue(
        path,
        { token: saved.token, name: saved.original_name, size: saved.size_bytes },
        { shouldDirty: true },
      );
      clearErrors(path);
    } catch (error) {
      setProblem(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!current) return;
    setProblem(null);
    if (!isExisting(current.token)) {
      void api(`/api/public/uploads/${current.token}`, { method: "DELETE" }).catch(() => {});
    }
    setValue(path, null, { shouldDirty: true });
  }

  return (
    <div className="border-portal-line flex flex-col gap-1.5 border-b py-3 last:border-b-0">
      <div className="flex items-center justify-between gap-3">
        <span className="text-[15px] leading-snug">
          {rule.label}
          {rule.note && <span className="text-portal-muted"> ({rule.note})</span>}
        </span>
        <button
          type="button"
          disabled={busy}
          onClick={() => input.current?.click()}
          className="border-portal-blue text-portal-blue hover:bg-portal-tint h-11 shrink-0 rounded-md border bg-white px-3.5 text-[15px] font-semibold disabled:opacity-50"
        >
          {busy ? "Uploading…" : current ? "Replace" : "Upload"}
        </button>
        <input
          ref={input}
          type="file"
          accept="application/pdf,image/jpeg,image/png"
          className="sr-only"
          tabIndex={-1}
          aria-label={`Upload ${rule.label}`}
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) void choose(file);
          }}
        />
      </div>
      {help && <Help>{help}</Help>}
      {children}
      {current && (
        <p className="text-portal-ok flex items-center justify-between gap-3 text-[13px] font-medium">
          <span className="min-w-0 truncate">
            Uploaded: {current.name} ({formatSize(current.size)})
          </span>
          {!isExisting(current.token) && (
            <button type="button" onClick={remove} className="text-portal-blue shrink-0 underline">
              Remove
            </button>
          )}
        </p>
      )}
      <ErrorText>{problem ?? fieldError}</ErrorText>
    </div>
  );
}
