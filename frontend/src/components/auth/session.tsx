"use client";

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { api, ApiError, errorMessage, homePathFor, type Me } from "@/lib/api";

type Session = { me: Me; logout: () => Promise<void> };

const SessionContext = createContext<Session | null>(null);

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) throw new Error("useSession must be used inside SessionGate");
  return session;
}

type State = { kind: "loading" } | { kind: "ready"; me: Me } | { kind: "error"; message: string };

/**
 * Shows its children only to a logged-in officer.
 * This is a convenience for the user: the API checks every request itself.
 */
export function SessionGate({
  children,
  adminOnly = false,
}: {
  children: React.ReactNode;
  adminOnly?: boolean;
}) {
  const router = useRouter();
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    api<Me>("/api/auth/me")
      .then((me) => {
        if (cancelled) return;
        if (me.must_change_password) {
          router.replace("/change-password");
        } else if (adminOnly && me.role !== "STATE_ADMIN") {
          router.replace(homePathFor(me));
        } else {
          setState({ kind: "ready", me });
        }
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 401) {
          router.replace("/login");
        } else {
          setState({ kind: "error", message: errorMessage(error) });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [router, adminOnly]);

  const logout = useCallback(async () => {
    try {
      await api("/api/auth/logout", { method: "POST" });
    } finally {
      router.replace("/login");
    }
  }, [router]);

  if (state.kind === "loading") {
    return <p className="text-muted-foreground p-6 text-sm">Loading…</p>;
  }
  if (state.kind === "error") {
    return (
      <p role="alert" className="text-destructive p-6 text-sm">
        {state.message}
      </p>
    );
  }
  return <SessionContext value={{ me: state.me, logout }}>{children}</SessionContext>;
}
