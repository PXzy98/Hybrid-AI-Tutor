import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, useState, type FormEvent } from "react";

import { ApiError } from "@/api/client";
import { api, type AdminStudent, type Staff, type SystemSettings, type SystemValues } from "@/api/endpoints";
import { useMe } from "@/auth";
import { ErrorNote, Loading, PageHeader, StatCard, StatusText } from "@/components/common";
import ModelEndpoints, { endpointsKey } from "@/components/ModelEndpoints";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useI18n } from "@/i18n";
import { useFormat } from "@/lib/format";

/** System administration: instructor accounts, system settings and model connections. Only the link is hidden for
 * other roles; every request below is checked by the server. */
export default function Admin() {
  const { t } = useI18n();
  const { data: me } = useMe();
  if (me && me.system_role !== "admin") return <p role="alert" className="text-destructive">{t("admin.forbidden")}</p>;
  return (
    <div className="space-y-6">
      <PageHeader level={1} title={t("admin.title")} />
      <UsageCard />
      <StaffCard selfId={me?.account_id} />
      <StudentAccountsCard />
      <SystemSettingsCard />
      <ModelEndpoints courseId={null} />
    </div>
  );
}

/** v5 V2: students and questions of every course, and the totals (counts only; small groups hidden). */
function UsageCard() {
  const { t } = useI18n();
  const stats = useQuery({ queryKey: ["system-statistics"], queryFn: api.systemStatistics });
  const data = stats.data;
  const show = (n: number | null | undefined) => (n == null ? t("overview.hidden") : n);
  return (
    <Card aria-label={t("usage.adminTitle")}>
      <CardHeader><CardTitle>{t("usage.adminTitle")}</CardTitle><CardDescription>{t("usage.hint", { n: data?.min_group ?? 5 })}</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        <ErrorNote error={stats.error} />
        {stats.isLoading && <Loading variant="table" />}
        {data && (
          <>
            <div className="grid gap-4 sm:grid-cols-3">
              <StatCard label={t("usage.enrolled")} value={data.students_enrolled} />
              <StatCard label={t("usage.active7d")} value={show(data.active_students_7d)} />
              <StatCard label={t("usage.questions7d")} value={show(data.questions_7d)} />
            </div>
            <Table aria-label={t("usage.perCourse")}>
              <TableHeader><TableRow>
                <TableHead>{t("usage.course")}</TableHead><TableHead>{t("usage.enrolled")}</TableHead>
                <TableHead>{t("usage.active7d")}</TableHead><TableHead>{t("usage.questions7d")}</TableHead><TableHead>{t("usage.questionsTotal")}</TableHead>
              </TableRow></TableHeader>
              <TableBody>{data.courses.map((c) => (
                <TableRow key={c.course_id}>
                  <TableCell><span className="font-medium">{c.code}</span> <span className="text-muted-foreground">{c.title}</span>
                    {c.status === "archived" && <Badge variant="secondary" className="ml-2">{t("usage.archived")}</Badge>}</TableCell>
                  <TableCell className="tabular-nums">{c.students_enrolled}</TableCell>
                  <TableCell className="tabular-nums">{show(c.active_students_7d)}</TableCell>
                  <TableCell className="tabular-nums">{show(c.questions_7d)}</TableCell>
                  <TableCell className="tabular-nums">{show(c.questions_total)}</TableCell>
                </TableRow>
              ))}</TableBody>
            </Table>
          </>
        )}
      </CardContent>
    </Card>
  );
}

type StudentAccount = AdminStudent;

/** V9: student accounts across courses. Accounts stay from term to term (the next class list finds them); an
 *  account that left is deactivated or deleted with its learning data. */
function StudentAccountsCard() {
  const { t } = useI18n();
  const fmt = useFormat();
  const qc = useQueryClient();
  const students = useQuery({ queryKey: ["admin-students"], queryFn: api.students });
  const refresh = () => qc.invalidateQueries({ queryKey: ["admin-students"] });
  const refreshAll = () => { refresh(); qc.invalidateQueries({ queryKey: ["system-statistics"] }); };
  const [search, setSearch] = useState("");
  const [temporary, setTemporary] = useState<{ id: number; name: string; password: string } | null>(null);
  const [pendingDelete, setPendingDelete] = useState<StudentAccount | null>(null);
  const [pendingReset, setPendingReset] = useState<StudentAccount | null>(null);
  const update = useMutation({ mutationFn: (a: StudentAccount) => api.updateStudent(a.account_id, !a.active), onSuccess: refreshAll });
  const reset = useMutation({
    mutationFn: async (a: StudentAccount) => ({ id: a.account_id, name: a.display_name, password: (await api.resetStudentPassword(a.account_id)).temporary_password }),
    onSuccess: setTemporary,
    onError: () => setTemporary(null),
  });
  const remove = useMutation({ mutationFn: (a: StudentAccount) => api.deleteStudent(a.account_id), onSuccess: (_, a) => {
      setPendingDelete(null);
      setTemporary((cur) => (cur?.id === a.account_id ? null : cur));
      refreshAll();
    },
  });
  const askDelete = (a: StudentAccount | null) => { remove.reset(); setPendingDelete(a); };
  const query = search.trim().toLowerCase();
  const shown = (students.data ?? []).filter((a) => !query || a.display_name.toLowerCase().includes(query) || (a.email ?? "").toLowerCase().includes(query));
  return (
    <Card>
      <CardHeader><CardTitle>{t("admin.students")}</CardTitle><CardDescription>{t("admin.studentsHint")}</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        <ErrorNote error={students.error ?? update.error ?? reset.error} />
        <div className="grid gap-1.5 sm:max-w-sm">
          <Label htmlFor="stu-search">{t("admin.searchStudents")}</Label>
          <Input id="stu-search" type="search" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        {students.isLoading && <Loading variant="table" />}
        {students.data && shown.length === 0 && <p className="text-sm text-muted-foreground">{t("admin.noStudents")}</p>}
        {shown.length > 0 && (
          <Table aria-label={t("admin.students")}>
            <TableHeader><TableRow>
              <TableHead>{t("members.name")}</TableHead><TableHead>{t("members.email")}</TableHead>
              <TableHead>{t("admin.courses")}</TableHead><TableHead>{t("admin.lastLogin")}</TableHead><TableHead>{t("members.status")}</TableHead>
              <TableHead><span className="sr-only">{t("students.actions")}</span></TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {shown.map((a) => (
                <Fragment key={a.account_id}>
                <TableRow>
                  <TableCell className="font-medium">{a.display_name}</TableCell>
                  <TableCell className="break-words">{a.email ?? "—"}</TableCell>
                  <TableCell className="tabular-nums">{a.courses}</TableCell>
                  <TableCell>{a.last_login_at ? fmt.date(a.last_login_at) : "—"}</TableCell>
                  <TableCell><Badge variant={a.active ? "success" : "secondary"}>{t(a.active ? "admin.active" : "admin.disabled")}</Badge></TableCell>
                  <TableCell className="space-x-1 whitespace-nowrap text-right">
                    <Button type="button" size="sm" variant="outline" aria-label={t(a.active ? "admin.disableFor" : "admin.enableFor", { name: a.display_name })}
                            onClick={() => { setTemporary(null); update.mutate(a); }}>{t(a.active ? "admin.disable" : "admin.enable")}</Button>
                    <Button type="button" size="sm" variant="outline" aria-label={t("admin.resetFor", { name: a.display_name })}
                            onClick={() => { setTemporary(null); setPendingReset(a); }}>{t("members.reset")}</Button>
                    <Button type="button" size="sm" variant="outline" className="text-destructive" aria-label={t("admin.deleteStudentFor", { name: a.display_name })}
                            onClick={() => askDelete(a)}>{t("admin.deleteStudent")}</Button>
                  </TableCell>
                </TableRow>
                {temporary?.id === a.account_id && <TemporaryRow columns={6} temporary={temporary} />}
                </Fragment>
              ))}
            </TableBody>
          </Table>
        )}
        <ResetDialog name={pendingReset?.display_name} onClose={() => setPendingReset(null)}
                     onConfirm={() => { if (pendingReset) reset.mutate(pendingReset); setPendingReset(null); }} />
        <Dialog open={!!pendingDelete} onOpenChange={(o) => { if (!o) askDelete(null); }}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t("admin.deleteStudentTitle")}</DialogTitle>
              <DialogDescription>{t("admin.deleteStudentBody", { name: pendingDelete?.display_name ?? "" })}</DialogDescription>
            </DialogHeader>
            <ErrorNote error={remove.error} />
            <DialogFooter>
              <DialogClose asChild><Button type="button" variant="outline">{t("end.cancel")}</Button></DialogClose>
              <Button type="button" variant="destructive" loading={remove.isPending} onClick={() => pendingDelete && remove.mutate(pendingDelete)}>{t("admin.deleteStudentConfirm")}</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}

/** A new temporary password, shown once (V17 W11: next to the account it belongs to). */
function TemporaryNote({ temporary }: { temporary: { name: string; password: string } }) {
  const { t } = useI18n();
  return (
    <Alert variant="warning" role="status">
      {t("members.temporary", { name: temporary.name })} <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-foreground">{temporary.password}</code>
      <p className="mt-1 text-xs">{t("admin.temporaryHint")}</p>
    </Alert>
  );
}

function TemporaryRow({ columns, temporary }: { columns: number; temporary: { name: string; password: string } }) {
  return <TableRow><TableCell colSpan={columns} className="whitespace-normal"><TemporaryNote temporary={temporary} /></TableCell></TableRow>;
}

/** A reset ends the current password at once, so it is confirmed first (V17 W11). */
function ResetDialog({ name, onClose, onConfirm }: { name?: string; onClose: () => void; onConfirm: () => void }) {
  const { t } = useI18n();
  return (
    <Dialog open={name !== undefined} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("admin.resetTitle")}</DialogTitle>
          <DialogDescription>{t("admin.resetBody", { name: name ?? "" })}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild><Button type="button" variant="outline">{t("end.cancel")}</Button></DialogClose>
          <Button type="button" onClick={onConfirm}>{t("admin.resetConfirm")}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function StaffCard({ selfId }: { selfId?: number }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const staff = useQuery({ queryKey: ["admin-staff"], queryFn: api.staff });
  const refresh = () => qc.invalidateQueries({ queryKey: ["admin-staff"] });
  const [temporary, setTemporary] = useState<{ id: number; name: string; password: string } | null>(null);
  const [pendingReset, setPendingReset] = useState<Staff | null>(null);
  const [form, setForm] = useState({ email: "", display_name: "", role: "instructor" as Staff["role"] });
  const create = useMutation({
    mutationFn: () => api.createStaff(form),
    onSuccess: (a) => {
      setTemporary({ id: a.account_id, name: a.display_name, password: a.temporary_password });
      setForm({ email: "", display_name: "", role: "instructor" });
      refresh();
    },
  });
  const update = useMutation({ mutationFn: (v: { id: number; changes: { active?: boolean; role?: Staff["role"] } }) => api.updateStaff(v.id, v.changes), onSuccess: refresh });
  const reset = useMutation({
    mutationFn: async (a: Staff) => ({ id: a.account_id, name: a.display_name, password: (await api.resetStaffPassword(a.account_id)).temporary_password }),
    onSuccess: setTemporary,
  });
  return (
    <Card>
      <CardHeader><CardTitle>{t("admin.staff")}</CardTitle><CardDescription>{t("admin.staffHint")}</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        <ErrorNote error={staff.error ?? update.error ?? reset.error} />
        {/* a new account is shown here until the list has it; a reset is shown under its row */}
        {temporary && !staff.data?.some((a) => a.account_id === temporary.id) && <TemporaryNote temporary={temporary} />}
        {!!staff.data?.length && (
          <Table>
            <TableHeader><TableRow>
              <TableHead>{t("members.name")}</TableHead><TableHead>{t("members.email")}</TableHead>
              <TableHead>{t("members.role")}</TableHead><TableHead>{t("members.status")}</TableHead>
              <TableHead><span className="sr-only">{t("students.actions")}</span></TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {staff.data.map((a) => (
                <Fragment key={a.account_id}>
                <TableRow>
                  <TableCell className="font-medium">{a.display_name}</TableCell>
                  <TableCell>{a.email ?? "—"}</TableCell>
                  <TableCell>
                    <Select aria-label={t("admin.roleOf", { name: a.display_name })} className="min-w-36" value={a.role} disabled={a.account_id === selfId}
                            onChange={(e) => update.mutate({ id: a.account_id, changes: { role: e.target.value as Staff["role"] } })}>
                      <option value="instructor">{t("role.instructor")}</option>
                      <option value="admin">{t("role.admin")}</option>
                    </Select>
                  </TableCell>
                  <TableCell><Badge variant={a.active ? "success" : "secondary"}>{t(a.active ? "admin.active" : "admin.disabled")}</Badge></TableCell>
                  <TableCell className="space-x-1 text-right">
                    <Button type="button" size="sm" variant="outline" disabled={a.account_id === selfId}
                            aria-label={t(a.active ? "admin.disableFor" : "admin.enableFor", { name: a.display_name })}
                            onClick={() => update.mutate({ id: a.account_id, changes: { active: !a.active } })}>{t(a.active ? "admin.disable" : "admin.enable")}</Button>
                    <Button type="button" size="sm" variant="outline" aria-label={t("admin.resetFor", { name: a.display_name })}
                            onClick={() => { setTemporary(null); setPendingReset(a); }}>{t("members.reset")}</Button>
                  </TableCell>
                </TableRow>
                {temporary?.id === a.account_id && <TemporaryRow columns={5} temporary={temporary} />}
                </Fragment>
              ))}
            </TableBody>
          </Table>
        )}
        <ResetDialog name={pendingReset?.display_name} onClose={() => setPendingReset(null)}
                     onConfirm={() => { if (pendingReset) reset.mutate(pendingReset); setPendingReset(null); }} />
        <form className="grid gap-3 border-t pt-4 sm:grid-cols-3" aria-label={t("admin.addStaff")}
              onSubmit={(e: FormEvent) => { e.preventDefault(); create.mutate(); }}>
          <div className="grid gap-1.5"><Label htmlFor="st-email">{t("members.email")}</Label>
            <Input id="st-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required /></div>
          <div className="grid gap-1.5"><Label htmlFor="st-name">{t("admin.displayName")}</Label>
            <Input id="st-name" value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} required maxLength={100} /></div>
          <div className="grid gap-1.5"><Label htmlFor="st-role">{t("members.role")}</Label>
            <Select id="st-role" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Staff["role"] })}>
              <option value="instructor">{t("role.instructor")}</option>
              <option value="admin">{t("role.admin")}</option>
            </Select></div>
          <div className="space-y-2 sm:col-span-3">
            <ErrorNote error={create.error} />
            <Button type="submit" disabled={create.isPending}>{t("admin.addStaff")}</Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function SystemSettingsCard() {
  const { t } = useI18n();
  const settings = useQuery({
    queryKey: ["admin-settings"], queryFn: api.systemSettings,
    refetchInterval: (q) => (q.state.data?.apply_state === "applying" ? APPLY_POLL_MS : false),
  });
  const state = settings.data?.apply_state;
  // the apply status gives the reason of a rollback and keeps polling while a change is applying
  const status = useQuery({
    queryKey: ["admin-apply-status"], queryFn: api.applyStatus, enabled: state === "applying" || state === "failed",
    refetchInterval: state === "applying" ? APPLY_POLL_MS : false,
  });
  const [conflict, setConflict] = useState(false);
  // kept here: the form starts again from each new version (its key), and must still say "saved"
  const [saved, setSaved] = useState(false);
  return (
    <>
      <ErrorNote error={settings.error} />
      {conflict && <Alert variant="warning" role="alert">{t("settings.conflict")}</Alert>}
      {settings.isLoading && <Loading variant="form" />}
      {state === "applying" && <Alert variant="info" role="status">{t("admin.applying")}</Alert>}
      {state === "failed" && <Alert variant="destructive" role="alert">{t("admin.rolledBack", { reason: status.data?.error ?? "" })}</Alert>}
      {settings.data && <SystemSettingsForm key={`${settings.data.version}-${state}`} initial={settings.data} onConflict={setConflict}
                                                saved={saved} onSaved={setSaved} />}
    </>
  );
}

const APPLY_POLL_MS = 1500;
const splitTypes = (v: string) => v.split(",").map((s) => s.trim()).filter(Boolean);
const num = (v: string) => (v === "" ? null : Number(v));

/** Saves with the version that was read; a 409 means someone else saved first and the latest values are loaded. */
function SystemSettingsForm({ initial, onConflict, saved, onSaved }:
  { initial: SystemSettings; onConflict: (on: boolean) => void; saved: boolean; onSaved: (saved: boolean) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [values, setValues] = useState<SystemValues>(initial.values);
  const initialTypes = (initial.values.enabled_course_types ?? []).join(", ");
  const [types, setTypes] = useState(initialTypes);
  // untouched: keep what is stored ([] = course creation off, null = every type); typed: empty means every type
  const typesToSave = () => (types === initialTypes ? initial.values.enabled_course_types ?? null
                                                    : splitTypes(types).length ? splitTypes(types) : null);
  const endpoints = useQuery({ queryKey: endpointsKey(null), queryFn: () => api.modelEndpoints(null) });
  const save = useMutation({
    mutationFn: () => api.saveSystemSettings({ ...values, enabled_course_types: typesToSave() }, initial.version),
    onSuccess: (fresh) => { onConflict(false); onSaved(true); qc.setQueryData(["admin-settings"], fresh); },
    onError: (e) => {
      const stale = e instanceof ApiError && e.status === 409;
      onConflict(stale);
      if (stale) qc.invalidateQueries({ queryKey: ["admin-settings"] });
    },
  });
  const set = (patch: Partial<SystemValues>) => { setValues({ ...values, ...patch }); onSaved(false); };
  // V17 W9: an empty field uses the deployment's config value; show it instead of an empty box
  const shown = (v: unknown) => (v === null || v === undefined ? undefined : t("admin.defaultValue", { value: String(v) }));
  const d = initial.defaults;
  const pick = (kind: "trusted_local" | "external") => (endpoints.data ?? []).filter((e) => e.trust === kind);
  const endpointSelect = (id: string, key: "default_local_endpoint_id" | "default_cloud_endpoint_id", kind: "trusted_local" | "external") => (
    <Select id={id} value={values[key] ?? ""} onChange={(e) => set({ [key]: num(e.target.value) })}>
      <option value="">{t("admin.noDefault")}</option>
      {pick(kind).map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
    </Select>
  );
  function submit(e: FormEvent) {
    e.preventDefault();
    save.mutate();
  }
  return (
    <Card>
      <CardHeader><CardTitle>{t("admin.settings")}</CardTitle><CardDescription>{t("admin.settingsHint")}</CardDescription></CardHeader>
      <CardContent>
        <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2" aria-label={t("admin.settings")}>
          <p className="text-sm text-muted-foreground sm:col-span-2">{t("admin.applyState", { state: t(`admin.apply.${initial.apply_state}`) })}</p>
          <label className="flex items-start gap-2 text-sm sm:col-span-2">
            <input type="checkbox" className="mt-0.5 accent-primary" checked={!!(values.weak_evidence ?? d?.weak_evidence)} onChange={(e) => set({ weak_evidence: e.target.checked })} />
            <span className="font-medium">{t("admin.weakEvidence")}</span>
          </label>
          <div className="grid gap-1.5"><Label htmlFor="sys-basic">{t("admin.basicBelow")}</Label>
            <Input id="sys-basic" type="number" min={0} max={1} step={0.01} value={values.level_basic_below ?? ""} placeholder={shown(d?.level_basic_below)} onChange={(e) => set({ level_basic_below: num(e.target.value) })} /></div>
          <div className="grid gap-1.5"><Label htmlFor="sys-adv">{t("admin.advancedAbove")}</Label>
            <Input id="sys-adv" type="number" min={0} max={1} step={0.01} value={values.level_advanced_above ?? ""} placeholder={shown(d?.level_advanced_above)} onChange={(e) => set({ level_advanced_above: num(e.target.value) })} /></div>
          <div className="grid gap-1.5"><Label htmlFor="sys-hyst">{t("admin.hysteresis")}</Label>
            <Input id="sys-hyst" type="number" min={0} max={0.2} step={0.01} value={values.level_hysteresis ?? ""} placeholder={shown(d?.level_hysteresis)} onChange={(e) => set({ level_hysteresis: num(e.target.value) })} /></div>
          <div className="grid gap-1.5"><Label htmlFor="sys-method">{t("admin.routingMethod")}</Label>
            <Select id="sys-method" value={values.default_routing_method ?? d?.default_routing_method ?? "lr"} onChange={(e) => set({ default_routing_method: e.target.value as "lr" | "svm" })}>
              <option value="lr">{t("admin.methodLr")}</option>
              <option value="svm">{t("admin.methodSvm")}</option>
            </Select></div>
          <div className="grid gap-1.5"><Label htmlFor="sys-url">{t("admin.localUrl")}</Label>
            <Input id="sys-url" type="url" value={values.local_llm_url ?? ""} placeholder={shown(d?.local_llm_url)} onChange={(e) => set({ local_llm_url: e.target.value })} /></div>
          <div className="grid gap-1.5"><Label htmlFor="sys-llm">{t("admin.localModel")}</Label>
            <Input id="sys-llm" value={values.local_llm_model ?? ""} placeholder={shown(d?.local_llm_model)} onChange={(e) => set({ local_llm_model: e.target.value })} /></div>
          <div className="grid gap-1.5 sm:col-span-2"><Label htmlFor="sys-types">{t("admin.courseTypes")}</Label>
            <Input id="sys-types" value={types} placeholder={shown(d?.enabled_course_types?.join(", "))} onChange={(e) => { setTypes(e.target.value); onSaved(false); }} />
            <p className="text-xs text-muted-foreground">{t("admin.courseTypesHint")}</p>
            {initial.values.enabled_course_types?.length === 0 && types === "" && <p className="text-xs text-destructive">{t("admin.courseTypesNone")}</p>}</div>
          <div className="grid gap-1.5"><Label htmlFor="sys-dlocal">{t("admin.defaultLocal")}</Label>{endpointSelect("sys-dlocal", "default_local_endpoint_id", "trusted_local")}</div>
          <div className="grid gap-1.5"><Label htmlFor="sys-dcloud">{t("admin.defaultCloud")}</Label>{endpointSelect("sys-dcloud", "default_cloud_endpoint_id", "external")}</div>
          <div className="space-y-2 sm:col-span-2">
            <ErrorNote error={save.error instanceof ApiError && save.error.status === 409 ? null : save.error} />
            {saved && <StatusText>{t("settings.saved")}</StatusText>}
            <Button loading={save.isPending} type="submit" disabled={save.isPending || initial.apply_state === "applying"}>{save.isPending ? t("settings.saving") : t("settings.save")}</Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
