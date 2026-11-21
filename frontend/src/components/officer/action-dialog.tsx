"use client";

import { useState } from "react";

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
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { api } from "@/lib/api";
import { loadOfficer, saveOfficer, type OfficerDetail, type Option } from "@/lib/officer";

export type ActionSpec = {
  /** Path after /api/officer/applications/<id>/ */
  path: "forward" | "return" | "reject" | "working-status";
  title: string;
  description: string;
  confirmLabel: string;
  /** A list to choose from: reasons, or working statuses. */
  choice?: {
    label: string;
    field: "reason_id" | "working_status_id";
    options: Option[];
    empty: string;
  };
  /** A free-text box, and whether something must be given (a choice or text). */
  remarks?: { label: string; required: boolean };
  /** A second free-text box that must be filled, sent under its own name. */
  extra?: { label: string; field: string; help: string };
  /** A tick box, sent under its own name. */
  tick?: { label: string; field: string };
  destructive?: boolean;
};

/** One action on an application, with the officer's name and designation. */
export function ActionDialog({
  spec,
  applicationId,
  onClose,
  onDone,
}: {
  spec: ActionSpec;
  applicationId: number;
  onClose: () => void;
  onDone: (updated: OfficerDetail) => void;
}) {
  const [officer, setOfficer] = useState(loadOfficer);
  const [choice, setChoice] = useState("");
  const [remarks, setRemarks] = useState("");
  const [extra, setExtra] = useState("");
  const [ticked, setTicked] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (spec.remarks?.required && !choice && !remarks.trim()) {
      setProblem({
        message: spec.choice ? "Choose a reason or write a remark." : "Write the remarks.",
        rows: [],
      });
      return;
    }
    if (spec.extra && !extra.trim()) {
      setProblem({ message: `Write the ${spec.extra.label.toLowerCase()}.`, rows: [] });
      return;
    }
    setBusy(true);
    setProblem(null);
    try {
      saveOfficer(officer);
      const body: Record<string, unknown> = {
        officer_name: officer.name,
        officer_designation: officer.designation,
      };
      if (spec.choice) body[spec.choice.field] = choice ? Number(choice) : null;
      if (spec.remarks) body.remarks = remarks;
      if (spec.extra) body[spec.extra.field] = extra;
      if (spec.tick) body[spec.tick.field] = ticked;
      const updated = await api<OfficerDetail>(
        `/api/officer/applications/${applicationId}/${spec.path}`,
        { method: "POST", body },
      );
      onDone(updated);
    } catch (error) {
      setProblem(toProblem(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{spec.title}</DialogTitle>
          <DialogDescription>{spec.description}</DialogDescription>
        </DialogHeader>
        <form
          id="action-form"
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          <ProblemAlert problem={problem} />

          {spec.choice && (
            <div className="space-y-1.5">
              <Label htmlFor="action-choice">{spec.choice.label}</Label>
              <NativeSelect
                id="action-choice"
                className="w-full"
                value={choice}
                onChange={(event) => setChoice(event.target.value)}
              >
                <NativeSelectOption value="">{spec.choice.empty}</NativeSelectOption>
                {spec.choice.options.map((option) => (
                  <NativeSelectOption key={option.id} value={option.id}>
                    {option.name}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </div>
          )}

          {spec.remarks && (
            <div className="space-y-1.5">
              <Label htmlFor="action-remarks">{spec.remarks.label}</Label>
              <textarea
                id="action-remarks"
                rows={3}
                maxLength={1000}
                value={remarks}
                onChange={(event) => setRemarks(event.target.value)}
                className="border-input focus-visible:border-ring focus-visible:ring-ring/50 w-full rounded-lg border bg-transparent px-2.5 py-2 text-sm outline-none focus-visible:ring-3"
              />
            </div>
          )}

          {spec.extra && (
            <div className="space-y-1.5">
              <Label htmlFor="action-extra">{spec.extra.label}</Label>
              <textarea
                id="action-extra"
                rows={3}
                maxLength={1000}
                value={extra}
                onChange={(event) => setExtra(event.target.value)}
                className="border-input focus-visible:border-ring focus-visible:ring-ring/50 w-full rounded-lg border bg-transparent px-2.5 py-2 text-sm outline-none focus-visible:ring-3"
              />
              <p className="text-muted-foreground text-xs">{spec.extra.help}</p>
            </div>
          )}

          {spec.tick && (
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={ticked}
                onChange={(event) => setTicked(event.target.checked)}
              />
              {spec.tick.label}
            </label>
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="action-officer-name">Your name</Label>
              <Input
                id="action-officer-name"
                required
                maxLength={100}
                value={officer.name}
                onChange={(event) => setOfficer({ ...officer, name: event.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="action-officer-designation">Your designation</Label>
              <Input
                id="action-officer-designation"
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
            form="action-form"
            variant={spec.destructive ? "destructive" : "default"}
            disabled={busy}
          >
            {busy ? "Saving…" : spec.confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
