"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useSession } from "@/components/auth/session";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Page } from "@/lib/api";
import { formatDay } from "@/lib/apply";
import { daysLeft, type QueueItem, type Reference } from "@/lib/officer";
import { INSPECTION_LABELS } from "@/lib/status";
import { useFetch } from "@/lib/use-fetch";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 50;

const STATUSES = [
  ["PENDING_DTO", "Pending with DTO"],
  ["ON_HOLD_DUPLICATE_CLAIM", "On hold: duplicate claim"],
  ["PENDING_POLICE", "Pending with Police"],
  ["PENDING_DC", "Pending with DC Office"],
  ["RETURNED_TO_APPLICANT", "Returned to applicant"],
  ["APPROVED", "Approved"],
  ["REJECTED", "Rejected"],
  ["CANCELLED", "Cancelled"],
  ["EXPIRED", "Expired"],
];

function Flags({ item }: { item: QueueItem }) {
  return (
    <div className="flex flex-wrap gap-1">
      {item.needs_dc_specific_approval && (
        <Badge className="bg-amber-500 text-black">60 to 90 minutes</Badge>
      )}
      {item.inspection_status !== "PASSED" && item.status === "PENDING_DTO" && (
        <Badge variant="outline">
          {INSPECTION_LABELS[item.inspection_status] ?? item.inspection_status}
        </Badge>
      )}
      {item.is_duplicate_claim && <Badge variant="destructive">Duplicate claim</Badge>}
      {item.mobile_flagged && <Badge variant="destructive">Flagged mobile</Badge>}
    </div>
  );
}

function Rows({ items, showOffice }: { items: QueueItem[]; showOffice: boolean }) {
  return (
    <div className="rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Application</TableHead>
            <TableHead>Travel date</TableHead>
            <TableHead>Group leader</TableHead>
            <TableHead>Vehicle</TableHead>
            <TableHead>{showOffice ? "Status and office" : "Working status"}</TableHead>
            <TableHead>Notes</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => {
            const left = daysLeft(item.days_left);
            const open = ["PENDING_DTO", "PENDING_POLICE", "PENDING_DC"].includes(item.status);
            return (
              <TableRow key={item.id} className="align-top">
                <TableCell>
                  <Link
                    href={`/dashboard/application?id=${item.id}`}
                    className="font-mono font-medium underline underline-offset-4"
                  >
                    {item.application_number}
                  </Link>
                </TableCell>
                <TableCell>
                  <div>{formatDay(item.travel_date)}</div>
                  {open && (
                    <div
                      className={cn(
                        "text-xs",
                        left.urgent ? "font-semibold text-red-700" : "text-muted-foreground",
                      )}
                    >
                      {left.text}
                    </div>
                  )}
                </TableCell>
                <TableCell>
                  <div>{item.leader_name}</div>
                  <div className="text-muted-foreground text-xs">
                    {item.leader_mobile} · {item.total_people} people
                  </div>
                </TableCell>
                <TableCell>
                  <div className="font-mono">{item.vehicle_reg_number}</div>
                  <div className="text-muted-foreground text-xs">{item.origin_police_station}</div>
                </TableCell>
                <TableCell>
                  {showOffice ? (
                    <>
                      <div>{item.status_label}</div>
                      <div className="text-muted-foreground text-xs">{item.current_office}</div>
                    </>
                  ) : (
                    item.working_status
                  )}
                </TableCell>
                <TableCell>
                  <Flags item={item} />
                </TableCell>
              </TableRow>
            );
          })}
          {items.length === 0 && (
            <TableRow>
              <TableCell colSpan={6} className="text-muted-foreground">
                Nothing to show.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}

function useDebounced(value: string): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value.trim()), 300);
    return () => clearTimeout(timer);
  }, [value]);
  return debounced;
}

/** The work of an office: what is waiting for it, and everything it may look at. */
export function OfficeQueue() {
  const { me } = useSession();
  const [tab, setTab] = useState<"queue" | "all">("queue");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const term = useDebounced(search);

  const queueQuery = new URLSearchParams();
  if (term) queueQuery.set("search", term);
  const queue = useFetch<QueueItem[]>(`/api/officer/queue?${queueQuery}`);

  const allQuery = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
  if (term) allQuery.set("search", term);
  if (status) allQuery.set("status", status);
  const all = useFetch<Page<QueueItem>>(
    tab === "all" ? `/api/officer/applications?${allQuery}` : null,
  );

  const reference = useFetch<Reference>("/api/officer/reference");
  const claims = reference.data?.duplicate_claims ?? 0;

  const total = all.data?.total ?? 0;
  const lastPage = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const everything =
    me.role === "POLICE_STATION"
      ? "All applications of this station"
      : "All applications of the district";

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <h1 className="text-xl font-semibold tracking-tight">{me.office}</h1>
        <p className="text-muted-foreground text-sm">
          The queue shows applications waiting for your office, earliest travel date first.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="flex gap-1">
          <Button variant={tab === "queue" ? "default" : "outline"} onClick={() => setTab("queue")}>
            Work queue{queue.data ? ` (${queue.data.length})` : ""}
          </Button>
          <Button
            variant={tab === "all" ? "default" : "outline"}
            onClick={() => {
              setTab("all");
              setPage(1);
            }}
          >
            {everything}
          </Button>
          {me.role === "DTO" && (
            <Button
              variant={claims > 0 ? "destructive" : "outline"}
              render={<Link href="/dashboard/claims" />}
              nativeButton={false}
            >
              Duplicate claims ({claims})
            </Button>
          )}
        </div>
        <Input
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          placeholder="Application, vehicle or mobile number"
          aria-label="Search by application number, vehicle number or mobile number"
          className="max-w-xs"
        />
        {tab === "all" && (
          <NativeSelect
            value={status}
            aria-label="Status"
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
          >
            <NativeSelectOption value="">All statuses</NativeSelectOption>
            {STATUSES.map(([value, label]) => (
              <NativeSelectOption key={value} value={value}>
                {label}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        )}
      </div>

      {(queue.error || all.error) && (
        <p role="alert" className="text-destructive text-sm">
          {queue.error ?? all.error}
        </p>
      )}

      {tab === "queue" ? (
        <Rows items={queue.data ?? []} showOffice={false} />
      ) : (
        <>
          <Rows items={all.data?.items ?? []} showOffice />
          <div className="flex items-center justify-end gap-2 text-sm">
            <span className="text-muted-foreground">
              {total} application(s) · page {page} of {lastPage}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
            >
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
        </>
      )}
    </div>
  );
}
