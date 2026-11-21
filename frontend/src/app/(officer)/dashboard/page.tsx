"use client";

import { useSession } from "@/components/auth/session";
import { OfficeQueue } from "@/components/officer/queue";
import { RoleCard } from "@/components/officer/role-card";

const WORKFLOW_ROLES = ["DTO", "POLICE_STATION", "DC_OFFICE"];

export default function DashboardPage() {
  const { me } = useSession();
  // Viewers get their dashboards in a later phase; until then they see who they are.
  return WORKFLOW_ROLES.includes(me.role) ? <OfficeQueue /> : <RoleCard />;
}
