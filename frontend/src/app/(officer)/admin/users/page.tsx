"use client";

import { useEffect, useState } from "react";

import {
  CredentialDialog,
  PageHeading,
  ProblemAlert,
  toProblem,
  UploadButton,
  type Credential,
  type Problem,
} from "@/components/admin/common";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
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
import {
  api,
  download,
  formatIst,
  ROLE_LABELS,
  type District,
  type DtoOffice,
  type Page,
  type PoliceStation,
  type Role,
  type User,
  type UserStatus,
  type UserWithPassword,
} from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";

const PAGE_SIZE = 50;
const ROLES = Object.keys(ROLE_LABELS) as Role[];

const STATUS: Record<UserStatus, { label: string; className?: string }> = {
  ACTIVE: { label: "Active", className: "bg-emerald-600 text-white" },
  MUST_CHANGE_PASSWORD: { label: "Password issued", className: "bg-sky-600 text-white" },
  NO_PASSWORD: { label: "No password yet", className: "bg-amber-500 text-black" },
  LOCKED: { label: "Locked", className: "bg-red-600 text-white" },
  INACTIVE: { label: "Inactive" },
};

function StatusBadge({ status }: { status: UserStatus }) {
  const { label, className } = STATUS[status];
  return className ? (
    <Badge className={className}>{label}</Badge>
  ) : (
    <Badge variant="outline">{label}</Badge>
  );
}

function DistrictOptions({ districts }: { districts: District[] }) {
  return districts.map((district) => (
    <NativeSelectOption key={district.id} value={district.id}>
      {district.name}
    </NativeSelectOption>
  ));
}

// ------------------------------------------------------------- create dialog

function CreateUserDialog({
  open,
  districts,
  onClose,
  onCreated,
}: {
  open: boolean;
  districts: District[];
  onClose: () => void;
  onCreated: (created: UserWithPassword) => void;
}) {
  const [role, setRole] = useState<Role>("DTO");
  const [districtId, setDistrictId] = useState("");
  const [officeId, setOfficeId] = useState("");
  const [userId, setUserId] = useState("");
  const [officeName, setOfficeName] = useState("");
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);

  const needsDistrict = role === "DTO" || role === "POLICE_STATION" || role === "DC_OFFICE";
  const stations = useFetch<PoliceStation[]>(
    open && role === "POLICE_STATION" && districtId
      ? `/api/admin/police-stations?district_id=${districtId}`
      : null,
  );
  const offices = useFetch<DtoOffice[]>(
    open && role === "DTO" && districtId
      ? `/api/admin/dto-offices?district_id=${districtId}`
      : null,
  );

  const link: Record<string, number> = {};
  if (role === "DTO" && officeId) link.dto_office_id = Number(officeId);
  if (role === "POLICE_STATION" && officeId) link.police_station_id = Number(officeId);
  if ((role === "DC_OFFICE" || role === "VIEWER") && districtId)
    link.district_id = Number(districtId);

  const complete =
    role === "STATE_ADMIN" ||
    role === "VIEWER" ||
    (role === "DC_OFFICE" && !!districtId) ||
    ((role === "DTO" || role === "POLICE_STATION") && !!officeId);

  const query = new URLSearchParams({
    role,
    ...Object.fromEntries(Object.entries(link).map(([k, v]) => [k, String(v)])),
  });
  const suggestion = useFetch<{ user_id: string }>(
    open && complete ? `/api/admin/users/suggest-id?${query}` : null,
  );

  function reset(nextRole: Role) {
    setRole(nextRole);
    setDistrictId("");
    setOfficeId("");
    setUserId("");
    setOfficeName("");
    setProblem(null);
  }

  async function submit() {
    setBusy(true);
    setProblem(null);
    try {
      const created = await api<UserWithPassword>("/api/admin/users", {
        method: "POST",
        body: {
          role,
          ...link,
          user_id: userId.trim() || null,
          office_name: officeName.trim() || null,
        },
      });
      reset("DTO");
      onCreated(created);
    } catch (error) {
      setProblem(toProblem(error));
    } finally {
      setBusy(false);
    }
  }

  const officeOptions = role === "DTO" ? offices.data : stations.data;

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create user</DialogTitle>
          <DialogDescription>
            The portal generates the user ID and a password. The password is shown once.
          </DialogDescription>
        </DialogHeader>
        <form
          id="create-user-form"
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          <ProblemAlert problem={problem} />

          <div className="space-y-1.5">
            <Label htmlFor="new-role">Role</Label>
            <NativeSelect
              id="new-role"
              className="w-full"
              value={role}
              onChange={(event) => reset(event.target.value as Role)}
            >
              {ROLES.map((value) => (
                <NativeSelectOption key={value} value={value}>
                  {ROLE_LABELS[value]}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </div>

          {role !== "STATE_ADMIN" && (
            <div className="space-y-1.5">
              <Label htmlFor="new-district">District</Label>
              <NativeSelect
                id="new-district"
                className="w-full"
                required={needsDistrict}
                value={districtId}
                onChange={(event) => {
                  setDistrictId(event.target.value);
                  setOfficeId("");
                }}
              >
                <NativeSelectOption value="">
                  {role === "VIEWER" ? "Whole State" : "Choose a district"}
                </NativeSelectOption>
                <DistrictOptions districts={districts} />
              </NativeSelect>
              {role === "VIEWER" && (
                <p className="text-muted-foreground text-xs">
                  Leave as Whole State for a State-level viewer, or choose a district for an SP
                  office or other district viewer.
                </p>
              )}
            </div>
          )}

          {(role === "DTO" || role === "POLICE_STATION") && (
            <div className="space-y-1.5">
              <Label htmlFor="new-office">{role === "DTO" ? "DTO office" : "Police station"}</Label>
              <NativeSelect
                id="new-office"
                className="w-full"
                required
                disabled={!districtId}
                value={officeId}
                onChange={(event) => setOfficeId(event.target.value)}
              >
                <NativeSelectOption value="">
                  {districtId ? "Choose" : "Choose a district first"}
                </NativeSelectOption>
                {(officeOptions ?? []).map((office) => (
                  <NativeSelectOption key={office.id} value={office.id}>
                    {office.name}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </div>
          )}

          {(role === "VIEWER" || role === "STATE_ADMIN") && (
            <div className="space-y-1.5">
              <Label htmlFor="new-office-name">Office name (optional)</Label>
              <Input
                id="new-office-name"
                value={officeName}
                onChange={(event) => setOfficeName(event.target.value)}
                placeholder={role === "VIEWER" ? "for example SP Office, Tinsukia" : ""}
              />
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="new-user-id">User ID</Label>
            <Input
              id="new-user-id"
              value={userId}
              onChange={(event) => setUserId(event.target.value)}
              placeholder={complete ? (suggestion.data?.user_id ?? "") : ""}
              autoCapitalize="none"
              spellCheck={false}
            />
            <p className="text-muted-foreground text-xs">
              {complete && suggestion.data
                ? `Leave empty to use ${suggestion.data.user_id}.`
                : "Leave empty to use the generated user ID."}
            </p>
          </div>
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="create-user-form" disabled={busy || !complete}>
            Create user
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// -------------------------------------------------- first passwords dialog

function FirstPasswordsDialog({
  open,
  onClose,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const pending = useFetch<{ never_issued: number; issued_never_logged_in: number }>(
    open ? "/api/admin/users/pending-passwords" : null,
  );
  const [includeIssued, setIncludeIssued] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);

  const count = pending.data
    ? pending.data.never_issued + (includeIssued ? pending.data.issued_never_logged_in : 0)
    : 0;

  async function generate() {
    setBusy(true);
    setProblem(null);
    try {
      await download(
        `/api/admin/users/generate-passwords?include_never_logged_in=${includeIssued}`,
        { method: "POST" },
      );
      setIncludeIssued(false);
      onDone(
        `Passwords were generated for ${count} account(s). Check your downloads folder for the Excel file.`,
      );
    } catch (error) {
      setProblem(toProblem(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Generate first passwords</DialogTitle>
          <DialogDescription>
            The portal generates a password for every account that has none, and gives you one Excel
            file with the user IDs and passwords. The file cannot be downloaded again, so keep it
            safe and delete it after the passwords are distributed.
          </DialogDescription>
        </DialogHeader>
        <ProblemAlert problem={problem} />
        {pending.data && (
          <div className="space-y-3 text-sm">
            <p>
              Accounts with no password yet: <strong>{pending.data.never_issued}</strong>
            </p>
            <label className="flex items-start gap-2">
              <input
                type="checkbox"
                className="mt-0.5 size-4"
                checked={includeIssued}
                onChange={(event) => setIncludeIssued(event.target.checked)}
              />
              <span>
                Also issue new passwords to the {pending.data.issued_never_logged_in} account(s)
                that were given a password but have never logged in. Use this only if an earlier
                file was lost: their earlier passwords stop working.
              </span>
            </label>
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={busy || count === 0} onClick={generate}>
            {busy ? "Generating…" : `Generate for ${count} account(s)`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------- the page

export default function UsersPage() {
  const districts = useFetch<District[]>("/api/admin/districts");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [role, setRole] = useState("");
  const [districtId, setDistrictId] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const query = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
  if (debouncedSearch) query.set("search", debouncedSearch);
  if (role) query.set("role", role);
  if (districtId) query.set("district_id", districtId);
  const users = useFetch<Page<User>>(`/api/admin/users?${query}`);

  const [creating, setCreating] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [renaming, setRenaming] = useState<User | null>(null);
  const [newUserId, setNewUserId] = useState("");
  const [credential, setCredential] = useState<Credential | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [renameProblem, setRenameProblem] = useState<Problem | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<string | void>) {
    setBusy(true);
    setProblem(null);
    setNotice(null);
    try {
      const message = await action();
      if (message) setNotice(message);
      users.reload();
    } catch (error) {
      setProblem(toProblem(error));
    } finally {
      setBusy(false);
    }
  }

  const resetPassword = (user: User) => {
    const warning = `Reset the password of ${user.user_id}? The current password stops working and the officer is logged out.`;
    if (!window.confirm(warning)) return;
    void run(async () => {
      const result = await api<UserWithPassword>(`/api/admin/users/${user.id}/reset-password`, {
        method: "POST",
      });
      setCredential({
        userId: result.user.user_id,
        password: result.password,
        office: result.user.office,
      });
    });
  };

  const setActive = (user: User, isActive: boolean) => {
    if (!isActive && !window.confirm(`Deactivate ${user.user_id}? The officer is logged out.`)) {
      return;
    }
    void run(async () => {
      await api(`/api/admin/users/${user.id}`, { method: "PATCH", body: { is_active: isActive } });
    });
  };

  const bulkCreate = (file: File) => {
    const form = new FormData();
    form.append("file", file);
    void run(async () => {
      await download("/api/admin/users/bulk", { method: "POST", form });
      return "The users were created. Check your downloads folder for the Excel file with their user IDs and passwords. It cannot be downloaded again.";
    });
  };

  async function rename() {
    if (!renaming) return;
    setBusy(true);
    setRenameProblem(null);
    try {
      await api(`/api/admin/users/${renaming.id}`, {
        method: "PATCH",
        body: { user_id: newUserId },
      });
      setRenaming(null);
      users.reload();
    } catch (error) {
      setRenameProblem(toProblem(error));
    } finally {
      setBusy(false);
    }
  }

  const total = users.data?.total ?? 0;
  const lastPage = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-4">
      <PageHeading
        title="Users"
        description="Officer accounts. Passwords are generated by the portal and must be changed at first login."
      >
        <Button variant="outline" onClick={() => setGenerating(true)}>
          Generate first passwords
        </Button>
        <Button onClick={() => setCreating(true)}>Create user</Button>
      </PageHeading>

      <div className="text-muted-foreground flex flex-wrap items-center gap-2 text-xs">
        <span>
          Bulk creation: fill the template with one row per user, then upload it. If any row has a
          problem, no users are created.
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void run(() => download("/api/admin/users/bulk-template"))}
        >
          Download template
        </Button>
        <UploadButton label="Upload list" disabled={busy} onFile={bulkCreate} />
      </div>

      <ProblemAlert problem={problem} />
      {users.error && <ProblemAlert problem={{ message: users.error, rows: [] }} />}
      {notice && (
        <Alert>
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search user ID"
          aria-label="Search user ID"
          className="max-w-xs"
        />
        <NativeSelect
          value={role}
          aria-label="Role"
          onChange={(event) => {
            setRole(event.target.value);
            setPage(1);
          }}
        >
          <NativeSelectOption value="">All roles</NativeSelectOption>
          {ROLES.map((value) => (
            <NativeSelectOption key={value} value={value}>
              {ROLE_LABELS[value]}
            </NativeSelectOption>
          ))}
        </NativeSelect>
        <NativeSelect
          value={districtId}
          aria-label="District"
          onChange={(event) => {
            setDistrictId(event.target.value);
            setPage(1);
          }}
        >
          <NativeSelectOption value="">All districts</NativeSelectOption>
          <DistrictOptions districts={districts.data ?? []} />
        </NativeSelect>
        <span className="text-muted-foreground text-sm">
          {users.data ? `${total} user(s)` : "Loading…"}
        </span>
      </div>

      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>User ID</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Office</TableHead>
              <TableHead>District</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Last login</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(users.data?.items ?? []).map((user) => (
              <TableRow key={user.id}>
                <TableCell className="font-mono">{user.user_id}</TableCell>
                <TableCell>{ROLE_LABELS[user.role]}</TableCell>
                <TableCell>{user.office}</TableCell>
                <TableCell>{user.district_name ?? "State"}</TableCell>
                <TableCell>
                  <StatusBadge status={user.status} />
                </TableCell>
                <TableCell>{formatIst(user.last_login_at) || "Never"}</TableCell>
                <TableCell>
                  <div className="flex justify-end gap-1">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busy}
                      onClick={() => resetPassword(user)}
                    >
                      Reset password
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setRenameProblem(null);
                        setNewUserId(user.user_id);
                        setRenaming(user);
                      }}
                    >
                      Rename
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={busy}
                      onClick={() => setActive(user, !user.is_active)}
                    >
                      {user.is_active ? "Deactivate" : "Activate"}
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {users.data && users.data.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-muted-foreground">
                  No users match.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-end gap-2 text-sm">
        <span className="text-muted-foreground">
          Page {page} of {lastPage}
        </span>
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={page >= lastPage}
          onClick={() => setPage(page + 1)}
        >
          Next
        </Button>
      </div>

      <CreateUserDialog
        open={creating}
        districts={districts.data ?? []}
        onClose={() => setCreating(false)}
        onCreated={(created) => {
          setCreating(false);
          setCredential({
            userId: created.user.user_id,
            password: created.password,
            office: created.user.office,
          });
          users.reload();
        }}
      />

      <FirstPasswordsDialog
        open={generating}
        onClose={() => setGenerating(false)}
        onDone={(message) => {
          setGenerating(false);
          setNotice(message);
          users.reload();
        }}
      />

      <Dialog open={renaming !== null} onOpenChange={(isOpen) => !isOpen && setRenaming(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rename {renaming?.user_id}</DialogTitle>
            <DialogDescription>
              {renaming?.office}. The password and the office stay the same. The officer logs in
              with the new user ID from now on.
            </DialogDescription>
          </DialogHeader>
          <form
            id="rename-form"
            className="space-y-1.5"
            onSubmit={(event) => {
              event.preventDefault();
              void rename();
            }}
          >
            <ProblemAlert problem={renameProblem} />
            <Label htmlFor="rename-user-id">New user ID</Label>
            <Input
              id="rename-user-id"
              required
              value={newUserId}
              onChange={(event) => setNewUserId(event.target.value)}
              autoCapitalize="none"
              spellCheck={false}
            />
            <p className="text-muted-foreground text-xs">
              Lowercase letters, digits and dots only.
            </p>
          </form>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRenaming(null)}>
              Cancel
            </Button>
            <Button type="submit" form="rename-form" disabled={busy}>
              Rename
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <CredentialDialog credential={credential} onClose={() => setCredential(null)} />
    </div>
  );
}
