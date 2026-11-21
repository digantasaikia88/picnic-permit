"use client";

import { useId, useMemo, useState } from "react";

import {
  ActiveBadge,
  CredentialDialog,
  PageHeading,
  ProblemAlert,
  toProblem,
  UploadButton,
  type Credential,
  type Problem,
} from "@/components/admin/common";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, type District, type UserWithPassword } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";

type Row = { id: number; name: string; is_active: boolean; district_id?: number } & Record<
  string,
  unknown
>;

export type MasterField = {
  name: string;
  label: string;
  /** "boolean" is a tick box, ticked for a new row. */
  type: "text" | "number" | "district" | "boolean";
  help?: string;
};

type Props = {
  title: string;
  description: string;
  /** What one row is called, for example "police station". */
  noun: string;
  endpoint: string;
  fields: MasterField[];
  /** Column names of the bulk upload file. Leave out for a master with no bulk upload. */
  bulkColumns?: string;
  /** Show a district filter (for rows that belong to a district). */
  filterByDistrict?: boolean;
  /** The request that creates the office's user ID for a newly added row. */
  userFor?: (row: Row) => Record<string, unknown>;
  /** Shown after a row is added, to tell the admin what to do next. */
  afterAddNote?: string;
  /** Added to the address when listing, for example "kind=RETURN". */
  listQuery?: string;
  /** Sent with every new row, for example the kind of a reason. */
  createExtra?: Record<string, unknown>;
};

type Editing = { mode: "add" } | { mode: "edit"; row: Row };

export function MasterTable({
  title,
  description,
  noun,
  endpoint,
  fields,
  bulkColumns,
  filterByDistrict = false,
  userFor,
  afterAddNote,
  listQuery,
  createExtra,
}: Props) {
  const formId = useId();
  const rows = useFetch<Row[]>(listQuery ? `${endpoint}?${listQuery}` : endpoint);
  const districts = useFetch<District[]>("/api/admin/districts");
  const [search, setSearch] = useState("");
  const [districtFilter, setDistrictFilter] = useState("");
  const [editing, setEditing] = useState<Editing | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [formProblem, setFormProblem] = useState<Problem | null>(null);
  const [pageProblem, setPageProblem] = useState<Problem | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [added, setAdded] = useState<Row | null>(null);
  const [credential, setCredential] = useState<Credential | null>(null);

  const districtName = useMemo(() => {
    const names = new Map((districts.data ?? []).map((d) => [d.id, d.name]));
    return (id: unknown) => names.get(Number(id)) ?? "";
  }, [districts.data]);

  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return (rows.data ?? []).filter((row) => {
      if (districtFilter && String(row.district_id) !== districtFilter) return false;
      if (!needle) return true;
      return fields.some((field) => {
        if (field.type === "boolean") return false;
        const value = field.type === "district" ? districtName(row[field.name]) : row[field.name];
        return String(value ?? "")
          .toLowerCase()
          .includes(needle);
      });
    });
  }, [rows.data, search, districtFilter, fields, districtName]);

  function open(next: Editing) {
    setFormProblem(null);
    setValues(
      Object.fromEntries(
        fields.map((field) => [
          field.name,
          next.mode === "edit"
            ? String(next.row[field.name] ?? "")
            : field.type === "boolean"
              ? "true"
              : "",
        ]),
      ),
    );
    setEditing(next);
  }

  function body(): Record<string, unknown> {
    return Object.fromEntries(
      fields.map((field) => [
        field.name,
        field.type === "text"
          ? values[field.name]
          : field.type === "boolean"
            ? values[field.name] === "true"
            : Number(values[field.name]),
      ]),
    );
  }

  async function save() {
    if (!editing) return;
    setBusy(true);
    setFormProblem(null);
    try {
      if (editing.mode === "add") {
        const row = await api<Row>(endpoint, {
          method: "POST",
          body: { ...body(), ...createExtra },
        });
        setAdded(row);
      } else {
        await api<Row>(`${endpoint}/${editing.row.id}`, { method: "PATCH", body: body() });
      }
      setEditing(null);
      rows.reload();
    } catch (error) {
      setFormProblem(toProblem(error));
    } finally {
      setBusy(false);
    }
  }

  async function run(action: () => Promise<string | void>) {
    setBusy(true);
    setPageProblem(null);
    setNotice(null);
    try {
      const message = await action();
      if (message) setNotice(message);
      rows.reload();
    } catch (error) {
      setPageProblem(toProblem(error));
    } finally {
      setBusy(false);
    }
  }

  const setActive = (row: Row, isActive: boolean) =>
    run(async () => {
      await api(`${endpoint}/${row.id}`, { method: "PATCH", body: { is_active: isActive } });
    });

  const remove = (row: Row) => {
    if (!window.confirm(`Delete ${row.name}? This cannot be undone.`)) return;
    void run(async () => {
      await api(`${endpoint}/${row.id}`, { method: "DELETE" });
      return `${row.name} was deleted.`;
    });
  };

  const upload = (file: File) => {
    const form = new FormData();
    form.append("file", file);
    void run(async () => {
      const result = await api<{ added: number; skipped: number }>(`${endpoint}/bulk`, {
        method: "POST",
        form,
      });
      return `Bulk upload: ${result.added} added, ${result.skipped} already present.`;
    });
  };

  async function createUser(row: Row) {
    if (!userFor) return;
    setBusy(true);
    setPageProblem(null);
    try {
      const created = await api<UserWithPassword>("/api/admin/users", {
        method: "POST",
        body: userFor(row),
      });
      setAdded(null);
      setCredential({
        userId: created.user.user_id,
        password: created.password,
        office: created.user.office,
      });
    } catch (error) {
      setAdded(null);
      setPageProblem(toProblem(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <PageHeading title={title} description={description}>
        {bulkColumns && <UploadButton label="Bulk upload" disabled={busy} onFile={upload} />}
        <Button onClick={() => open({ mode: "add" })}>Add {noun}</Button>
      </PageHeading>

      {bulkColumns && (
        <p className="text-muted-foreground text-xs">
          Bulk upload takes an Excel or CSV file with the columns: {bulkColumns}. Rows already
          present are skipped. If any row has a problem, nothing is added.
        </p>
      )}

      <ProblemAlert problem={pageProblem} />
      {rows.error && <ProblemAlert problem={{ message: rows.error, rows: [] }} />}
      {notice && (
        <Alert>
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search"
          aria-label="Search"
          className="max-w-xs"
        />
        {filterByDistrict && (
          <NativeSelect
            value={districtFilter}
            onChange={(event) => setDistrictFilter(event.target.value)}
            aria-label="District"
          >
            <NativeSelectOption value="">All districts</NativeSelectOption>
            {(districts.data ?? []).map((district) => (
              <NativeSelectOption key={district.id} value={district.id}>
                {district.name}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        )}
        <span className="text-muted-foreground text-sm">
          {rows.data ? `${visible.length} of ${rows.data.length}` : "Loading…"}
        </span>
      </div>

      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              {fields.map((field) => (
                <TableHead key={field.name}>{field.label}</TableHead>
              ))}
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {visible.map((row) => (
              <TableRow key={row.id}>
                {fields.map((field) => (
                  <TableCell key={field.name}>
                    {field.type === "district"
                      ? districtName(row[field.name])
                      : field.type === "boolean"
                        ? row[field.name]
                          ? "Yes"
                          : "No"
                        : String(row[field.name] ?? "")}
                  </TableCell>
                ))}
                <TableCell>
                  <ActiveBadge active={row.is_active} />
                </TableCell>
                <TableCell>
                  <div className="flex justify-end gap-1">
                    <Button variant="outline" size="sm" onClick={() => open({ mode: "edit", row })}>
                      Edit
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busy}
                      onClick={() => setActive(row, !row.is_active)}
                    >
                      {row.is_active ? "Deactivate" : "Activate"}
                    </Button>
                    <Button variant="ghost" size="sm" disabled={busy} onClick={() => remove(row)}>
                      Delete
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {rows.data && visible.length === 0 && (
              <TableRow>
                <TableCell colSpan={fields.length + 2} className="text-muted-foreground">
                  Nothing to show.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={editing !== null} onOpenChange={(isOpen) => !isOpen && setEditing(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing?.mode === "edit" ? `Edit ${noun}` : `Add ${noun}`}</DialogTitle>
            <DialogDescription>Every change is recorded in the change log.</DialogDescription>
          </DialogHeader>
          <form
            id={formId}
            className="space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              void save();
            }}
          >
            <ProblemAlert problem={formProblem} />
            {fields
              .filter((field) => field.type !== "boolean")
              .map((field) => (
                <div key={field.name} className="space-y-1.5">
                  <Label htmlFor={`field-${field.name}`}>{field.label}</Label>
                  {field.type === "district" ? (
                    <NativeSelect
                      id={`field-${field.name}`}
                      className="w-full"
                      required
                      value={values[field.name] ?? ""}
                      onChange={(event) =>
                        setValues((old) => ({ ...old, [field.name]: event.target.value }))
                      }
                    >
                      <NativeSelectOption value="">Choose a district</NativeSelectOption>
                      {(districts.data ?? []).map((district) => (
                        <NativeSelectOption key={district.id} value={district.id}>
                          {district.name}
                        </NativeSelectOption>
                      ))}
                    </NativeSelect>
                  ) : (
                    <Input
                      id={`field-${field.name}`}
                      required
                      inputMode={field.type === "number" ? "numeric" : undefined}
                      pattern={field.type === "number" ? "[0-9]+" : undefined}
                      value={values[field.name] ?? ""}
                      onChange={(event) =>
                        setValues((old) => ({ ...old, [field.name]: event.target.value }))
                      }
                    />
                  )}
                  {field.help && <p className="text-muted-foreground text-xs">{field.help}</p>}
                </div>
              ))}
            {fields
              .filter((field) => field.type === "boolean")
              .map((field) => (
                <label key={field.name} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={values[field.name] === "true"}
                    onChange={(event) =>
                      setValues((old) => ({ ...old, [field.name]: String(event.target.checked) }))
                    }
                  />
                  {field.help ?? field.label}
                </label>
              ))}
          </form>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditing(null)}>
              Cancel
            </Button>
            <Button type="submit" form={formId} disabled={busy}>
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={added !== null} onOpenChange={(isOpen) => !isOpen && setAdded(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{added?.name} was added</DialogTitle>
            <DialogDescription>
              {userFor
                ? "Create its user ID now? The portal will generate the user ID and a password."
                : ""}{" "}
              {afterAddNote}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAdded(null)}>
              {userFor ? "Not now" : "Close"}
            </Button>
            {userFor && added && (
              <Button disabled={busy} onClick={() => createUser(added)}>
                Create user ID
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <CredentialDialog credential={credential} onClose={() => setCredential(null)} />
    </div>
  );
}
