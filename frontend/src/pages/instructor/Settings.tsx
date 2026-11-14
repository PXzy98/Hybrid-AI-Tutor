import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent, type ReactNode } from "react";

import { ApiError } from "@/api/client";
import { api, type Course, type CourseSettings, type CourseValues } from "@/api/endpoints";
import { ErrorNote, Loading, StatusText } from "@/components/common";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import ModelEndpoints, { endpointsKey } from "@/components/ModelEndpoints";
import { useI18n } from "@/i18n";

/** Course settings: title and term, then the privacy and routing values. The save sends the version that was
 * read; the server answers 409 if someone else changed it. */
export default function Settings({ course }: { course: Course }) {
  const settings = useQuery({ queryKey: ["settings", course.id], queryFn: () => api.courseSettings(course.id) });
  return (
    <div className="max-w-3xl space-y-6">
      <CourseInfo course={course} />
      <ErrorNote error={settings.error} />
      {settings.isLoading && <Loading variant="form" />}
      {settings.data && <SettingsForm key={settings.data.version} course={course} initial={settings.data} />}
      <ModelEndpoints courseId={course.id} />
      <ArchiveCourse course={course} />
    </div>
  );
}

/** Archive the course. The server refuses (409) while the course still has students: end the term first. */
function ArchiveCourse({ course }: { course: Course }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const archive = useMutation({
    mutationFn: () => api.archiveCourse(course.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["courses"] }),
  });
  const refused = archive.error instanceof ApiError && archive.error.status === 409;
  return (
    <Card>
      <CardHeader><CardTitle>{t("archive.title")}</CardTitle><CardDescription>{t("archive.hint")}</CardDescription></CardHeader>
      <CardContent className="space-y-3">
        {refused && <Alert variant="warning" role="alert" icon>{t("archive.refused")} {(archive.error as ApiError).message}</Alert>}
        <ErrorNote error={refused ? null : archive.error} />
        {course.status === "archived"
          ? <p className="text-sm text-muted-foreground">{t("archive.done")}</p>
          : <Button type="button" variant="outline" onClick={() => archive.mutate()} loading={archive.isPending}>{t("archive.button")}</Button>}
      </CardContent>
    </Card>
  );
}

function CourseInfo({ course }: { course: Course }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [form, setForm] = useState({ code: course.code, title: course.title, term_label: course.term_label });
  const save = useMutation({
    mutationFn: () => api.updateCourse(course.id, form),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["courses"] }),
  });
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });
  return (
    <Card>
      <CardHeader><CardTitle>{t("course.info")}</CardTitle></CardHeader>
      <CardContent>
        <form className="grid gap-4 sm:grid-cols-3" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
          <div className="grid gap-1.5"><Label htmlFor="ci-code">{t("course.code")}</Label><Input id="ci-code" value={form.code} onChange={set("code")} required /></div>
          <div className="grid gap-1.5"><Label htmlFor="ci-title">{t("course.title")}</Label><Input id="ci-title" value={form.title} onChange={set("title")} required /></div>
          <div className="grid gap-1.5"><Label htmlFor="ci-term">{t("course.term")}</Label><Input id="ci-term" value={form.term_label} onChange={set("term_label")} /></div>
          <div className="sm:col-span-3 space-y-2">
            <ErrorNote error={save.error} />
            {save.isSuccess && <StatusText>{t("settings.saved")}</StatusText>}
            <Button type="submit" loading={save.isPending}>{t("settings.save")}</Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function SettingsForm({ course, initial }: { course: Course; initial: CourseSettings }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [values, setValues] = useState<CourseValues>(initial.values);
  const endpoints = useQuery({ queryKey: endpointsKey(course.id), queryFn: () => api.modelEndpoints(course.id) });
  const pick = (trust: "trusted_local" | "external") => (endpoints.data ?? []).filter((e) => e.trust === trust);
  const save = useMutation({
    mutationFn: () => api.saveCourseSettings(course.id, values, initial.version),
    onSuccess: (fresh) => {
      qc.setQueryData(["settings", course.id], fresh);
      qc.invalidateQueries({ queryKey: ["courses"] });
    },
  });
  const conflict = save.error instanceof ApiError && save.error.status === 409;
  const dirty = JSON.stringify(values) !== JSON.stringify(initial.values);
  function submit(e: FormEvent) {
    e.preventDefault();
    save.mutate();
  }
  const field = "grid gap-1.5 sm:max-w-sm";
  return (
    <form onSubmit={submit} className="space-y-4" aria-labelledby="set-title">
      <div className="space-y-1">
        <h3 id="set-title" className="text-base font-semibold">{t("settings.title")}</h3>
        <p className="text-sm text-muted-foreground">{t("settings.hint")}</p>
      </div>
      <SettingsGroup title={t("settings.group.visibility")}>
        <div className={field}>
          <Label htmlFor="set-visibility">{t("settings.visibility")}</Label>
          <Select id="set-visibility" value={values.visibility_mode ?? course.visibility_mode}
                  onChange={(e) => setValues({ ...values, visibility_mode: e.target.value as "A" | "B" })}>
            <option value="A">{t("settings.visibilityA")}</option>
            <option value="B">{t("settings.visibilityB")}</option>
          </Select>
        </div>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-0.5 accent-primary" checked={!!values.local_only}
                 onChange={(e) => setValues({ ...values, local_only: e.target.checked })} />
          <span><span className="font-medium">{t("settings.localOnly")}</span><br /><span className="text-muted-foreground">{t("settings.localOnlyHint")}</span></span>
        </label>
      </SettingsGroup>
      <SettingsGroup title={t("settings.group.models")}>
        <div className={field}>
          <Label htmlFor="set-routing">{t("settings.routing")}</Label>
          <Select id="set-routing" value={values.routing_preference ?? "default"}
                  onChange={(e) => setValues({ ...values, routing_preference: e.target.value as CourseValues["routing_preference"] })}>
            <option value="default">{t("settings.routingDefault")}</option>
            <option value="prefer_local">{t("settings.routingLocal")}</option>
            <option value="prefer_cloud">{t("settings.routingCloud")}</option>
          </Select>
        </div>
        <div className={field}>
          <Label htmlFor="set-local-endpoint">{t("settings.localEndpoint")}</Label>
          <Select id="set-local-endpoint" value={values.local_endpoint_id ?? ""}
                  onChange={(e) => setValues({ ...values, local_endpoint_id: e.target.value === "" ? null : Number(e.target.value) })}>
            <option value="">{t("settings.useDefault")}</option>
            {pick("trusted_local").map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
          </Select>
        </div>
        <div className={field}>
          <Label htmlFor="set-cloud-endpoint">{t("settings.cloudEndpoint")}</Label>
          <Select id="set-cloud-endpoint" value={values.cloud_endpoint_id ?? ""}
                  onChange={(e) => setValues({ ...values, cloud_endpoint_id: e.target.value === "" ? null : Number(e.target.value) })}>
            <option value="">{t("settings.useDefault")}</option>
            {pick("external").map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
          </Select>
        </div>
      </SettingsGroup>
      <SettingsGroup title={t("settings.group.display")}>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-0.5 accent-primary" checked={values.show_routing_progress ?? true}
                 onChange={(e) => setValues({ ...values, show_routing_progress: e.target.checked })} />
          <span className="font-medium">{t("settings.showProgress")}</span>
        </label>
      </SettingsGroup>
      {conflict && <Alert variant="warning" icon>{t("settings.conflict")}</Alert>}
      <ErrorNote error={conflict ? null : save.error} />
      {/* stays at the bottom of the content area while the groups scroll */}
      <div className="sticky bottom-0 z-10 flex flex-wrap items-center gap-3 border-t bg-background py-3">
        <Button loading={save.isPending} type="submit" disabled={save.isPending}>{save.isPending ? t("settings.saving") : t("settings.save")}</Button>
        {dirty && !save.isPending && <span className="text-xs text-muted-foreground">{t("form.unsaved")}</span>}
        {!dirty && save.isSuccess && <StatusText>{t("settings.saved")}</StatusText>}
      </div>
    </form>
  );
}

/** One titled group of the settings form, in its own card. */
function SettingsGroup({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card>
      <CardHeader><CardTitle aria-level={4}>{title}</CardTitle></CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
    </Card>
  );
}
