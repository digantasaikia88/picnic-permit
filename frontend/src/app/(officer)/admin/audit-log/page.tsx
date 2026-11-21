"use client";

import { useState } from "react";

import { PageHeading, ProblemAlert } from "@/components/admin/common";
import { Button } from "@/components/ui/button";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatIst, type AuditRow, type Page } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";

const PAGE_SIZE = 50;

const ENTITY_TYPES = [
  { value: "user", label: "Users" },
  { value: "district", label: "Districts" },
  { value: "police_station", label: "Police stations" },
  { value: "dto_office", label: "DTO offices" },
  { value: "setting", label: "Settings" },
];

function Values({ value }: { value: Record<string, unknown> | null }) {
  if (!value || Object.keys(value).length === 0) return null;
  return (
    <ul className="space-y-0.5">
      {Object.entries(value).map(([key, item]) => (
        <li key={key}>
          <span className="text-muted-foreground">{key}:</span> {String(item)}
        </li>
      ))}
    </ul>
  );
}

export default function AuditLogPage() {
  const [entityType, setEntityType] = useState("");
  const [page, setPage] = useState(1);

  const query = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
  if (entityType) query.set("entity_type", entityType);
  const log = useFetch<Page<AuditRow>>(`/api/admin/audit-log?${query}`);

  const total = log.data?.total ?? 0;
  const lastPage = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-4">
      <PageHeading
        title="Change log"
        description="Every action and data change: who, when, old value and new value. Rows cannot be edited or deleted."
      />
      {log.error && <ProblemAlert problem={{ message: log.error, rows: [] }} />}

      <div className="flex flex-wrap items-center gap-2">
        <NativeSelect
          value={entityType}
          aria-label="Show"
          onChange={(event) => {
            setEntityType(event.target.value);
            setPage(1);
          }}
        >
          <NativeSelectOption value="">Everything</NativeSelectOption>
          {ENTITY_TYPES.map((type) => (
            <NativeSelectOption key={type.value} value={type.value}>
              {type.label}
            </NativeSelectOption>
          ))}
        </NativeSelect>
        <span className="text-muted-foreground text-sm">
          {log.data ? `${total} row(s), newest first` : "Loading…"}
        </span>
      </div>

      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>When (IST)</TableHead>
              <TableHead>Who</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>On</TableHead>
              <TableHead>Old value</TableHead>
              <TableHead>New value</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(log.data?.items ?? []).map((row) => (
              <TableRow key={row.id} className="align-top">
                <TableCell className="whitespace-nowrap">{formatIst(row.at)}</TableCell>
                <TableCell className="font-mono">{row.actor}</TableCell>
                <TableCell>{row.action}</TableCell>
                <TableCell>{row.entity_label}</TableCell>
                <TableCell>
                  <Values value={row.old_value} />
                </TableCell>
                <TableCell>
                  <Values value={row.new_value} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-end gap-2 text-sm">
        <span className="text-muted-foreground">
          Page {page} of {lastPage}
        </span>
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={page >= lastPage}
          onClick={() => setPage(page + 1)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
