"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useSession } from "@/components/auth/session";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/users", label: "Users" },
  { href: "/admin/districts", label: "Districts" },
  { href: "/admin/police-stations", label: "Police stations" },
  { href: "/admin/dto-offices", label: "DTO offices" },
  { href: "/admin/vehicle-types", label: "Vehicle types" },
  { href: "/admin/emergency-contacts", label: "Emergency contacts" },
  { href: "/admin/working-statuses", label: "Working statuses" },
  { href: "/admin/remark-reasons", label: "Reasons" },
  { href: "/admin/flagged-mobiles", label: "Flagged mobiles" },
  { href: "/admin/settings", label: "Settings" },
  { href: "/admin/audit-log", label: "Change log" },
];

export function AdminShell({ children }: { children: React.ReactNode }) {
  const { me } = useSession();
  const pathname = usePathname();

  // The API refuses non-admins on every admin request; this only avoids a page of errors.
  if (me.role !== "STATE_ADMIN") {
    return (
      <p role="alert" className="text-sm">
        This area is for State User Management Admins.{" "}
        <Link href="/dashboard">Go to your page</Link>.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <nav aria-label="Admin" className="-mx-1 flex gap-1 overflow-x-auto border-b pb-2">
        {LINKS.map((link) => {
          const active =
            link.href === "/admin" ? pathname === "/admin" : pathname.startsWith(link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm whitespace-nowrap",
                active ? "bg-primary text-primary-foreground" : "hover:bg-muted",
              )}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>
      {children}
    </div>
  );
}
