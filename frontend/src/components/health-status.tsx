"use client";

import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getHealth, type Health } from "@/lib/api";

type State =
  { kind: "loading" } | { kind: "loaded"; health: Health } | { kind: "error"; message: string };

const timeFormat = new Intl.DateTimeFormat("en-IN", {
  dateStyle: "medium",
  timeStyle: "medium",
  timeZone: "Asia/Kolkata",
});

function StatusBadge({
  ok,
  okLabel,
  failLabel,
}: {
  ok: boolean;
  okLabel: string;
  failLabel: string;
}) {
  return ok ? (
    <Badge className="bg-emerald-600 text-white">{okLabel}</Badge>
  ) : (
    <Badge variant="destructive">{failLabel}</Badge>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <dt className="text-muted-foreground text-sm">{label}</dt>
      <dd className="text-sm font-medium">{children}</dd>
    </div>
  );
}

export function HealthStatus() {
  const [state, setState] = useState<State>({ kind: "loading" });

  const check = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      setState({ kind: "loaded", health: await getHealth() });
    } catch (error) {
      setState({
        kind: "error",
        message: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    getHealth()
      .then((health) => {
        if (!cancelled) setState({ kind: "loaded", health });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            kind: "error",
            message: error instanceof Error ? error.message : "Unknown error",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>System status</CardTitle>
        <CardDescription>Live result of GET /api/health</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="divide-y" aria-live="polite">
          <Row label="API">
            {state.kind === "loading" ? (
              <Badge variant="outline">Checking…</Badge>
            ) : (
              <StatusBadge
                ok={state.kind === "loaded"}
                okLabel="Reachable"
                failLabel="Not reachable"
              />
            )}
          </Row>
          <Row label="Database">
            {state.kind === "loading" ? (
              <Badge variant="outline">Checking…</Badge>
            ) : state.kind === "loaded" ? (
              <StatusBadge
                ok={state.health.database === "ok"}
                okLabel="Connected"
                failLabel="Not reachable"
              />
            ) : (
              <Badge variant="outline">Unknown</Badge>
            )}
          </Row>
          {state.kind === "loaded" && (
            <>
              <Row label="Environment">
                <span className="capitalize">{state.health.environment}</span>
              </Row>
              <Row label="Checked at (IST)">
                {timeFormat.format(new Date(state.health.checked_at))}
              </Row>
            </>
          )}
        </dl>
        {state.kind === "error" && (
          <p role="alert" className="text-destructive mt-3 text-sm">
            Could not reach the API: {state.message}
          </p>
        )}
      </CardContent>
      <CardFooter>
        <Button
          variant="outline"
          className="w-full sm:w-auto"
          onClick={check}
          disabled={state.kind === "loading"}
        >
          Check again
        </Button>
      </CardFooter>
    </Card>
  );
}
