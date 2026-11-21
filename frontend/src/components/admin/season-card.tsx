"use client";

import { useState } from "react";

import { ProblemAlert, toProblem, type Problem } from "@/components/admin/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";

type Season = { start_date: string | null; end_date: string | null };

function SeasonForm({ season, onSaved }: { season: Season; onSaved: () => void }) {
  const [start, setStart] = useState(season.start_date ?? "");
  const [end, setEnd] = useState(season.end_date ?? "");
  const [problem, setProblem] = useState<Problem | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  async function save(startDate: string, endDate: string) {
    setBusy(true);
    setProblem(null);
    setSaved(false);
    try {
      await api("/api/admin/season", {
        method: "PUT",
        body: { start_date: startDate || null, end_date: endDate || null },
      });
      setSaved(true);
      onSaved();
    } catch (error) {
      setProblem(toProblem(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="space-y-3"
      onSubmit={(event) => {
        event.preventDefault();
        void save(start, end);
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="season-start">Start date</Label>
          <Input
            id="season-start"
            type="date"
            value={start}
            onChange={(event) => setStart(event.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="season-end">End date</Label>
          <Input
            id="season-end"
            type="date"
            value={end}
            onChange={(event) => setEnd(event.target.value)}
          />
        </div>
      </div>
      <ProblemAlert problem={problem} />
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" disabled={busy}>
          Save season
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={busy || (!season.start_date && !season.end_date)}
          onClick={() => {
            setStart("");
            setEnd("");
            void save("", "");
          }}
        >
          Remove the season limit
        </Button>
        {saved && <span className="text-sm text-emerald-700">Saved.</span>}
      </div>
    </form>
  );
}

/** The picnic season: journeys can be applied for only on dates inside it. */
export function SeasonCard() {
  const season = useFetch<Season>("/api/admin/season");

  return (
    <Card>
      <CardHeader>
        <CardTitle>Picnic season</CardTitle>
        <CardDescription>
          The date of travel must fall within the season. While no dates are set, any date allowed
          by the minimum and maximum days before travel can be chosen.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {season.error && <ProblemAlert problem={{ message: season.error, rows: [] }} />}
        {season.data && (
          <SeasonForm
            key={`${season.data.start_date}:${season.data.end_date}`}
            season={season.data}
            onSaved={season.reload}
          />
        )}
      </CardContent>
    </Card>
  );
}
