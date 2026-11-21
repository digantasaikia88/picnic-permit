"use client";

import Link from "next/link";

import { PageHeading } from "@/components/admin/common";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { District, DtoOffice, Page, PoliceStation, User } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";

function CountCard({
  href,
  title,
  count,
  note,
}: {
  href: string;
  title: string;
  count: number | undefined;
  note: string;
}) {
  return (
    <Link href={href} className="focus-visible:ring-ring rounded-xl focus-visible:ring-2">
      <Card className="hover:bg-muted/50 h-full transition-colors">
        <CardHeader>
          <CardDescription>{title}</CardDescription>
          <CardTitle className="text-3xl tabular-nums">{count ?? "…"}</CardTitle>
        </CardHeader>
        <CardContent className="text-muted-foreground text-sm">{note}</CardContent>
      </Card>
    </Link>
  );
}

export default function AdminOverviewPage() {
  const districts = useFetch<District[]>("/api/admin/districts");
  const stations = useFetch<PoliceStation[]>("/api/admin/police-stations");
  const offices = useFetch<DtoOffice[]>("/api/admin/dto-offices");
  const users = useFetch<Page<User>>("/api/admin/users?page_size=1");
  const pending = useFetch<{ never_issued: number; issued_never_logged_in: number }>(
    "/api/admin/users/pending-passwords",
  );

  const active = <T extends { is_active: boolean }>(rows: T[] | undefined) =>
    rows ? `${rows.filter((row) => row.is_active).length} active` : "";

  return (
    <div className="space-y-6">
      <PageHeading
        title="Administration"
        description="Masters, officer accounts and settings of the Picnic Portal."
      />

      {pending.data && pending.data.never_issued > 0 && (
        <Alert>
          <AlertTitle>{pending.data.never_issued} account(s) have no password yet</AlertTitle>
          <AlertDescription>
            These officers cannot log in until you issue their first passwords. Go to{" "}
            <Link href="/admin/users">Users</Link> and choose Generate first passwords.
          </AlertDescription>
        </Alert>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <CountCard
          href="/admin/users"
          title="Users"
          count={users.data?.total}
          note="Officer, viewer and admin accounts"
        />
        <CountCard
          href="/admin/districts"
          title="Districts"
          count={districts.data?.length}
          note={active(districts.data)}
        />
        <CountCard
          href="/admin/police-stations"
          title="Police stations"
          count={stations.data?.length}
          note={active(stations.data)}
        />
        <CountCard
          href="/admin/dto-offices"
          title="DTO offices"
          count={offices.data?.length}
          note={active(offices.data)}
        />
      </div>
    </div>
  );
}
