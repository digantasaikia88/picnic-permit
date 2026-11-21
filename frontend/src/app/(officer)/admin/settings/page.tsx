"use client";

import { useState } from "react";

import { PageHeading, ProblemAlert, toProblem, type Problem } from "@/components/admin/common";
import { SeasonCard } from "@/components/admin/season-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, type Setting } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";

function SettingRow({ setting, onSaved }: { setting: Setting; onSaved: () => void }) {
  const [value, setValue] = useState(String(setting.value));
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);
  const changed = value !== String(setting.value);

  async function save() {
    setBusy(true);
    setProblem(null);
    try {
      await api(`/api/admin/settings/${setting.key}`, {
        method: "PATCH",
        body: { value: Number(value) },
      });
      onSaved();
    } catch (error) {
      setProblem(toProblem(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="space-y-2 py-4">
      <form
        className="flex flex-wrap items-center justify-between gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <label htmlFor={`setting-${setting.key}`} className="min-w-0 flex-1 basis-64 text-sm">
          <span className="font-medium">{setting.description}</span>
          <span className="text-muted-foreground block text-xs">
            Whole number from {setting.min_value} to {setting.max_value}
          </span>
        </label>
        <div className="flex items-center gap-2">
          <Input
            id={`setting-${setting.key}`}
            className="w-24 text-right tabular-nums"
            inputMode="numeric"
            pattern="[0-9]+"
            required
            value={value}
            onChange={(event) => setValue(event.target.value)}
          />
          <Button type="submit" variant="outline" disabled={busy || !changed}>
            Save
          </Button>
        </div>
      </form>
      <ProblemAlert problem={problem} />
    </li>
  );
}

export default function SettingsPage() {
  const settings = useFetch<Setting[]>("/api/admin/settings");

  return (
    <div className="max-w-2xl space-y-4">
      <PageHeading
        title="Settings"
        description="Values that can change without a code change. Every change is recorded in the change log."
      />
      <SeasonCard />
      {settings.error && <ProblemAlert problem={{ message: settings.error, rows: [] }} />}
      <ul className="divide-y">
        {(settings.data ?? []).map((setting) => (
          // The key includes the value so a saved row picks up its new starting value.
          <SettingRow
            key={`${setting.key}:${setting.value}`}
            setting={setting}
            onSaved={settings.reload}
          />
        ))}
      </ul>
    </div>
  );
}
