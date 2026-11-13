import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { ApiError } from "@/api/client";
import { api, type Staff, type SystemSettings, type SystemValues } from "@/api/endpoints";
import { useMe } from "@/auth";
import { ErrorNote } from "@/components/common";
import ModelEndpoints, { endpointsKey } from "@/components/ModelEndpoints";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useI18n } from "@/i18n";

/** System administration: instructor accounts, system settings and model connections. Only the link is hidden for
 * other roles; every request below is checked by the server. */
export default function Admin() {
  const { t } = useI18n();
  const { data: me } = useMe();
  if (me && me.system_role !== "admin") return <p role="alert" className="text-destructive">{t("admin.forbidden")}</p>;
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">{t("admin.title")}</h1>
      <StaffCard selfId={me?.account_id} />
      <SystemSettingsCard />
      <ModelEndpoints courseId={null} />
    </div>
  );
}

function StaffCard({ selfId }: { selfId?: number }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const staff = useQuery({ queryKey: ["admin-staff"], queryFn: api.staff });
  const refresh = () => qc.invalidateQueries({ queryKey: ["admin-staff"] });
  const [temporary, setTemporary] = useState<{ name: string; password: string } | null>(null);
  const [form, setForm] = useState({ email: "", display_name: "", role: "instructor" as Staff["role"] });
  const create = useMutation({
    mutationFn: () => api.createStaff(form),
    onSuccess: (a) => {
      setTemporary({ name: a.display_name, password: a.temporary_password });
      setForm({ email: "", display_name: "", role: "instructor" });
      refresh();
    },
  });
  const update = useMutation({ mutationFn: (v: { id: number; changes: { active?: boolean; role?: Staff["role"] } }) => api.updateStaff(v.id, v.changes), onSuccess: refresh });
  const reset = useMutation({
    mutationFn: async (a: Staff) => ({ name: a.display_name, password: (await api.resetStaffPassword(a.account_id)).temporary_password }),
    onSuccess: setTemporary,
  });
  return (
    <Card>
      <CardHeader><CardTitle>{t("admin.staff")}</CardTitle><CardDescription>{t("admin.staffHint")}</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        <ErrorNote error={staff.error ?? update.error ?? reset.error} />
        {temporary && (
          <Alert variant="warning" role="status">
            {t("members.temporary", { name: temporary.name })} <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-foreground">{temporary.password}</code>
            <p className="mt-1 text-xs">{t("admin.temporaryHint")}</p>
          </Alert>
        )}
        {!!staff.data?.length && (
          <Table>
            <TableHeader><TableRow>
              <TableHead>{t("members.name")}</TableHead><TableHead>{t("members.email")}</TableHead>
              <TableHead>{t("members.role")}</TableHead><TableHead>{t("members.status")}</TableHead>
              <TableHead><span className="sr-only">{t("students.actions")}</span></TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {staff.data.map((a) => (
                <TableRow key={a.account_id}>
                  <TableCell className="font-medium">{a.display_name}</TableCell>
                  <TableCell>{a.email ?? "—"}</TableCell>
                  <TableCell>
                    <Select aria-label={t("admin.roleOf", { name: a.display_name })} value={a.role} disabled={a.account_id === selfId}
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
                            onClick={() => reset.mutate(a)}>{t("members.reset")}</Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
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
  return (
    <>
      <ErrorNote error={settings.error} />
      {conflict && <Alert variant="warning" role="alert">{t("settings.conflict")}</Alert>}
      {settings.isLoading && <p className="text-muted-foreground">{t("app.loading")}</p>}
      {state === "applying" && <Alert variant="info" role="status">{t("admin.applying")}</Alert>}
      {state === "failed" && <Alert variant="destructive" role="alert">{t("admin.rolledBack", { reason: status.data?.error ?? "" })}</Alert>}
      {settings.data && <SystemSettingsForm key={`${settings.data.version}-${state}`} initial={settings.data} onConflict={setConflict} />}
    </>
  );
}

const APPLY_POLL_MS = 1500;
const splitTypes = (v: string) => v.split(",").map((s) => s.trim()).filter(Boolean);
const num = (v: string) => (v === "" ? null : Number(v));

/** Saves with the version that was read; a 409 means someone else saved first and the latest values are loaded. */
function SystemSettingsForm({ initial, onConflict }: { initial: SystemSettings; onConflict: (on: boolean) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [values, setValues] = useState<SystemValues>(initial.values);
  const [types, setTypes] = useState((initial.values.enabled_course_types ?? []).join(", "));
  const endpoints = useQuery({ queryKey: endpointsKey(null), queryFn: () => api.modelEndpoints(null) });
  const save = useMutation({
    mutationFn: () => api.saveSystemSettings({ ...values, enabled_course_types: splitTypes(types) }, initial.version),
    onSuccess: (fresh) => { onConflict(false); qc.setQueryData(["admin-settings"], fresh); },
    onError: (e) => {
      const stale = e instanceof ApiError && e.status === 409;
      onConflict(stale);
      if (stale) qc.invalidateQueries({ queryKey: ["admin-settings"] });
    },
  });
  const set = (patch: Partial<SystemValues>) => setValues({ ...values, ...patch });
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
            <input type="checkbox" className="mt-0.5 accent-primary" checked={!!values.weak_evidence} onChange={(e) => set({ weak_evidence: e.target.checked })} />
            <span className="font-medium">{t("admin.weakEvidence")}</span>
          </label>
          <div className="grid gap-1.5"><Label htmlFor="sys-basic">{t("admin.basicBelow")}</Label>
            <Input id="sys-basic" type="number" min={0} max={1} step={0.01} value={values.level_basic_below ?? ""} onChange={(e) => set({ level_basic_below: num(e.target.value) })} /></div>
          <div className="grid gap-1.5"><Label htmlFor="sys-adv">{t("admin.advancedAbove")}</Label>
            <Input id="sys-adv" type="number" min={0} max={1} step={0.01} value={values.level_advanced_above ?? ""} onChange={(e) => set({ level_advanced_above: num(e.target.value) })} /></div>
          <div className="grid gap-1.5"><Label htmlFor="sys-hyst">{t("admin.hysteresis")}</Label>
            <Input id="sys-hyst" type="number" min={0} max={0.2} step={0.01} value={values.level_hysteresis ?? ""} onChange={(e) => set({ level_hysteresis: num(e.target.value) })} /></div>
          <div className="grid gap-1.5"><Label htmlFor="sys-method">{t("admin.routingMethod")}</Label>
            <Select id="sys-method" value={values.default_routing_method ?? "lr"} onChange={(e) => set({ default_routing_method: e.target.value as "lr" | "svm" })}>
              <option value="lr">{t("admin.methodLr")}</option>
              <option value="svm">{t("admin.methodSvm")}</option>
            </Select></div>
          <div className="grid gap-1.5"><Label htmlFor="sys-url">{t("admin.localUrl")}</Label>
            <Input id="sys-url" type="url" value={values.local_llm_url ?? ""} onChange={(e) => set({ local_llm_url: e.target.value })} /></div>
          <div className="grid gap-1.5"><Label htmlFor="sys-llm">{t("admin.localModel")}</Label>
            <Input id="sys-llm" value={values.local_llm_model ?? ""} onChange={(e) => set({ local_llm_model: e.target.value })} /></div>
          <div className="grid gap-1.5 sm:col-span-2"><Label htmlFor="sys-types">{t("admin.courseTypes")}</Label>
            <Input id="sys-types" value={types} onChange={(e) => setTypes(e.target.value)} />
            <p className="text-xs text-muted-foreground">{t("admin.courseTypesHint")}</p></div>
          <div className="grid gap-1.5"><Label htmlFor="sys-dlocal">{t("admin.defaultLocal")}</Label>{endpointSelect("sys-dlocal", "default_local_endpoint_id", "trusted_local")}</div>
          <div className="grid gap-1.5"><Label htmlFor="sys-dcloud">{t("admin.defaultCloud")}</Label>{endpointSelect("sys-dcloud", "default_cloud_endpoint_id", "external")}</div>
          <div className="space-y-2 sm:col-span-2">
            <ErrorNote error={save.error instanceof ApiError && save.error.status === 409 ? null : save.error} />
            {save.isSuccess && <p role="status" className="text-sm text-emerald-700 dark:text-emerald-300">{t("settings.saved")}</p>}
            <Button type="submit" disabled={save.isPending || initial.apply_state === "applying"}>{save.isPending ? t("settings.saving") : t("settings.save")}</Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
