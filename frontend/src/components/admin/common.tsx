"use client";

import { useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ApiError, errorMessage } from "@/lib/api";

export type Problem = { message: string; rows: string[] };

export function toProblem(error: unknown): Problem {
  return {
    message: errorMessage(error),
    rows: error instanceof ApiError ? error.errors : [],
  };
}

/** An error, with the row-by-row problems of a bulk upload when there are any. */
export function ProblemAlert({ problem }: { problem: Problem | null }) {
  if (!problem) return null;
  return (
    <Alert variant="destructive">
      <AlertTitle>{problem.message}</AlertTitle>
      {problem.rows.length > 0 && (
        <AlertDescription>
          <ul className="list-disc space-y-0.5 pl-4">
            {problem.rows.map((row) => (
              <li key={row}>{row}</li>
            ))}
          </ul>
        </AlertDescription>
      )}
    </Alert>
  );
}

export function PageHeading({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div className="space-y-1">
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        <p className="text-muted-foreground text-sm">{description}</p>
      </div>
      {children && <div className="flex flex-wrap gap-2">{children}</div>}
    </div>
  );
}

export function ActiveBadge({ active }: { active: boolean }) {
  return active ? (
    <Badge className="bg-emerald-600 text-white">Active</Badge>
  ) : (
    <Badge variant="outline">Inactive</Badge>
  );
}

export type Credential = { userId: string; password: string; office: string };

/** Shows a generated password. It is shown once and cannot be fetched again. */
export function CredentialDialog({
  credential,
  onClose,
}: {
  credential: Credential | null;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    if (!credential) return;
    await navigator.clipboard.writeText(
      `User ID: ${credential.userId}\nPassword: ${credential.password}`,
    );
    setCopied(true);
  }

  return (
    <Dialog
      open={credential !== null}
      onOpenChange={(open) => {
        if (!open) {
          setCopied(false);
          onClose();
        }
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Password for {credential?.userId}</DialogTitle>
          <DialogDescription>
            {credential?.office}. Note it now and share it with the office. It is shown only once,
            and the officer must change it at the first login.
          </DialogDescription>
        </DialogHeader>
        <dl className="bg-muted space-y-2 rounded-lg p-3 text-sm">
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">User ID</dt>
            <dd className="font-mono font-medium">{credential?.userId}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">Password</dt>
            <dd className="font-mono font-medium select-all">{credential?.password}</dd>
          </div>
        </dl>
        <DialogFooter>
          <Button variant="outline" onClick={copy}>
            {copied ? "Copied" : "Copy"}
          </Button>
          <Button onClick={onClose}>Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** A file picker button for CSV or Excel uploads. */
export function UploadButton({
  label,
  disabled,
  onFile,
}: {
  label: string;
  disabled?: boolean;
  onFile: (file: File) => void;
}) {
  return (
    <label
      className={
        "border-border bg-background hover:bg-muted inline-flex h-8 cursor-pointer items-center rounded-lg border px-2.5 text-sm font-medium" +
        (disabled ? " pointer-events-none opacity-50" : "")
      }
    >
      {label}
      <input
        type="file"
        accept=".csv,.xlsx"
        className="sr-only"
        disabled={disabled}
        onChange={(event) => {
          const file = event.target.files?.[0];
          // Clear the picker so the same file can be chosen again after a fix.
          event.target.value = "";
          if (file) onFile(file);
        }}
      />
    </label>
  );
}
