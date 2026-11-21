"use client";

import { useId, useState } from "react";

import { ProblemAlert, toProblem, type Problem } from "@/components/admin/common";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { loadOfficer, saveOfficer } from "@/lib/officer";

export const textareaClass =
  "border-input focus-visible:border-ring focus-visible:ring-ring/50 w-full rounded-lg border bg-transparent px-2.5 py-2 text-sm outline-none focus-visible:ring-3";

/**
 * A form an office fills for an application. It adds the officer's name and
 * designation, sends the form, and hands back what the API answers.
 */
export function WorkDialog<T>({
  title,
  description,
  confirmLabel,
  url,
  build,
  onClose,
  onDone,
  destructive = false,
  wide = false,
  children,
}: {
  title: string;
  description: string;
  confirmLabel: string;
  /** Where the form is sent, for example /api/officer/applications/5/transfer */
  url: string;
  /** The form as the API expects it, or a message saying what is missing. */
  build: () => Record<string, unknown> | FormData | string;
  onClose: () => void;
  onDone: (result: T) => void;
  destructive?: boolean;
  wide?: boolean;
  children: React.ReactNode;
}) {
  const formId = useId();
  const [officer, setOfficer] = useState(loadOfficer);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    const body = build();
    if (typeof body === "string") {
      setProblem({ message: body, rows: [] });
      return;
    }
    setBusy(true);
    setProblem(null);
    try {
      saveOfficer(officer);
      let result: T;
      if (body instanceof FormData) {
        // A form with a file goes as a multipart form.
        body.set("officer_name", officer.name);
        body.set("officer_designation", officer.designation);
        result = await api<T>(url, { method: "POST", form: body });
      } else {
        result = await api<T>(url, {
          method: "POST",
          body: {
            ...body,
            officer_name: officer.name,
            officer_designation: officer.designation,
          },
        });
      }
      onDone(result);
    } catch (error) {
      setProblem(toProblem(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className={wide ? "max-h-[90vh] overflow-y-auto sm:max-w-2xl" : undefined}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <form
          id={formId}
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          <ProblemAlert problem={problem} />
          {children}
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor={`${formId}-name`}>Your name</Label>
              <Input
                id={`${formId}-name`}
                required
                maxLength={100}
                value={officer.name}
                onChange={(event) => setOfficer({ ...officer, name: event.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={`${formId}-designation`}>Your designation</Label>
              <Input
                id={`${formId}-designation`}
                required
                maxLength={100}
                value={officer.designation}
                onChange={(event) => setOfficer({ ...officer, designation: event.target.value })}
              />
            </div>
          </div>
          <p className="text-muted-foreground text-xs">
            Your name and designation are recorded with this action, and remembered on this
            computer.
          </p>
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            form={formId}
            variant={destructive ? "destructive" : "default"}
            disabled={busy}
          >
            {busy ? "Saving…" : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** A labelled free-text box. */
export function TextBox({
  label,
  value,
  onChange,
  rows = 2,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  rows?: number;
}) {
  const id = useId();
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <textarea
        id={id}
        rows={rows}
        maxLength={1000}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={textareaClass}
      />
    </div>
  );
}

/** One line of a checklist: a label and a small set of answers to pick from. */
export function ChoiceRow({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: Record<string, string>;
  onChange: (value: string) => void;
}) {
  const name = useId();
  return (
    <fieldset className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b py-1.5 last:border-b-0">
      <legend className="sr-only">{label}</legend>
      <span className="text-sm">{label}</span>
      <span className="flex flex-wrap gap-x-3 gap-y-1">
        {Object.entries(options).map(([key, text]) => (
          <label key={key} className="flex items-center gap-1 text-sm">
            <input
              type="radio"
              name={name}
              checked={value === key}
              onChange={() => onChange(key)}
            />
            {text}
          </label>
        ))}
      </span>
    </fieldset>
  );
}
