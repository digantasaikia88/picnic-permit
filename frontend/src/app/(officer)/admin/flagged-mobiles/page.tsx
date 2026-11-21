"use client";

import { useState } from "react";

import { PageHeading, ProblemAlert, toProblem, type Problem } from "@/components/admin/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, formatIst } from "@/lib/api";
import type { FlaggedMobile } from "@/lib/officer";
import { useFetch } from "@/lib/use-fetch";

export default function FlaggedMobilesPage() {
  const rows = useFetch<FlaggedMobile[]>("/api/admin/flagged-mobiles");
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setProblem(null);
    try {
      await action();
      rows.reload();
    } catch (error) {
      setProblem(toProblem(error));
    } finally {
      setBusy(false);
    }
  }

  const setBlocked = (row: FlaggedMobile, isBlocked: boolean) =>
    run(() =>
      api(`/api/admin/flagged-mobiles/${row.id}`, {
        method: "PATCH",
        body: { is_blocked: isBlocked },
      }),
    );

  const remove = (row: FlaggedMobile) => {
    if (!window.confirm(`Remove the flag from ${row.mobile}?`)) return;
    void run(() => api(`/api/admin/flagged-mobiles/${row.id}`, { method: "DELETE" }));
  };

  return (
    <div className="space-y-4">
      <PageHeading
        title="Flagged mobile numbers"
        description="A DTO flags the mobile number behind a fake or prank application. Officers then see a warning on its later applications. Block a number to stop it from applying at all."
      />
      <ProblemAlert problem={problem} />
      {rows.error && <ProblemAlert problem={{ message: rows.error, rows: [] }} />}

      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Mobile number</TableHead>
              <TableHead>Reason</TableHead>
              <TableHead>Flagged by</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(rows.data ?? []).map((row) => (
              <TableRow key={row.id} className="align-top">
                <TableCell className="font-mono">{row.mobile}</TableCell>
                <TableCell className="max-w-sm whitespace-normal">
                  {row.reason}
                  {row.application_number && (
                    <div className="text-muted-foreground text-xs">
                      Application {row.application_number}
                    </div>
                  )}
                </TableCell>
                <TableCell className="whitespace-normal">
                  {row.flagged_by}
                  <div className="text-muted-foreground text-xs">{formatIst(row.created_at)}</div>
                </TableCell>
                <TableCell>
                  {row.is_blocked ? (
                    <Badge variant="destructive">Blocked</Badge>
                  ) : (
                    <Badge variant="outline">Flagged</Badge>
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex justify-end gap-1">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busy}
                      onClick={() => setBlocked(row, !row.is_blocked)}
                    >
                      {row.is_blocked ? "Lift the block" : "Block from applying"}
                    </Button>
                    <Button variant="ghost" size="sm" disabled={busy} onClick={() => remove(row)}>
                      Remove flag
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {rows.data?.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-muted-foreground">
                  No mobile number is flagged.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
