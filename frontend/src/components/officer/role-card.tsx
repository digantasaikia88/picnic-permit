"use client";

import { useSession } from "@/components/auth/session";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ROLE_LABELS } from "@/lib/api";

const LEVEL_LABELS = {
  STATE: "Whole State",
  DISTRICT: "District",
  POLICE_STATION: "Police station",
} as const;

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <dt className="text-muted-foreground text-sm">{label}</dt>
      <dd className="text-right text-sm font-medium">{value}</dd>
    </div>
  );
}

/** Shown to users who have no work queue yet (viewers and admins). */
export function RoleCard() {
  const { me } = useSession();
  const jurisdiction =
    me.jurisdiction_level === "POLICE_STATION"
      ? `${me.police_station_name}, ${me.district_name}`
      : me.jurisdiction_level === "DISTRICT"
        ? (me.district_name ?? "")
        : "Assam";

  return (
    <div className="mx-auto max-w-md space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{me.office}</CardTitle>
          <CardDescription>You are logged in.</CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="divide-y">
            <Row label="User ID" value={me.user_id} />
            <Row label="Role" value={ROLE_LABELS[me.role]} />
            <Row label="Jurisdiction level" value={LEVEL_LABELS[me.jurisdiction_level]} />
            <Row label="Jurisdiction" value={jurisdiction} />
          </dl>
        </CardContent>
      </Card>
      <p className="text-muted-foreground text-xs">
        Work queues, applications and reports come in later phases.
      </p>
    </div>
  );
}
