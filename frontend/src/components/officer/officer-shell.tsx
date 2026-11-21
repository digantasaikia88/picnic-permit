"use client";

import Link from "next/link";

import { SessionGate, useSession } from "@/components/auth/session";
import { Button } from "@/components/ui/button";
import { homePathFor } from "@/lib/api";

function TopBar() {
  const { me, logout } = useSession();
  return (
    <header className="bg-background border-b">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3">
        <Link href={homePathFor(me)} className="font-semibold tracking-tight">
          Picnic Portal
        </Link>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          <span className="text-muted-foreground">
            {me.office} · <span className="text-foreground font-medium">{me.user_id}</span>
          </span>
          <Link href="/change-password" className="underline underline-offset-4">
            Change password
          </Link>
          <Button variant="outline" size="sm" onClick={logout}>
            Log out
          </Button>
        </div>
      </div>
    </header>
  );
}

export function OfficerShell({ children }: { children: React.ReactNode }) {
  return (
    <SessionGate>
      <TopBar />
      <div className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">{children}</div>
    </SessionGate>
  );
}
