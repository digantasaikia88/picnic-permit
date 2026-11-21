import Link from "next/link";

import { HealthStatus } from "@/components/health-status";

// A technical page: shows whether the API and the database are reachable.
export default function HealthPage() {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center gap-6 px-4 py-10">
      <header className="space-y-1">
        <p className="text-muted-foreground text-sm">Transport Department, Government of Assam</p>
        <h1 className="text-3xl font-semibold tracking-tight">Picnic Portal</h1>
        <p className="text-muted-foreground">System health</p>
      </header>
      <HealthStatus />
      <p className="text-sm">
        <Link href="/" className="underline underline-offset-4">
          Back to the home page
        </Link>
      </p>
    </main>
  );
}
