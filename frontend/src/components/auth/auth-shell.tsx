import Link from "next/link";

/** Centred frame for the login and change-password pages. */
export function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-6 px-4 py-10">
      <header className="space-y-1 text-center">
        <p className="text-muted-foreground text-sm">Transport Department, Government of Assam</p>
        <h1 className="text-2xl font-semibold tracking-tight">
          <Link href="/">Picnic Portal</Link>
        </h1>
      </header>
      {children}
    </main>
  );
}
