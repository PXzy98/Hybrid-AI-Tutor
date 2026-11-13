import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { ApiError } from "@/api/client";
import { api, type Course, type CourseSettings, type CourseValues } from "@/api/endpoints";
import { ErrorNote } from "@/components/common";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import ModelEndpoints from "@/components/ModelEndpoints";
import { useI18n } from "@/i18n";

/** Course settings: title and term, then the privacy and routing values. The save sends the version that was
 * read; the server answers 409 if someone else changed it. */
export default function Settings({ course }: { course: Course }) {
  const { t } = useI18n();
  const settings = useQuery({ queryKey: ["settings", course.id], queryFn: () => api.courseSettings(course.id) });
  return (
    <div className="space-y-4">
      <CourseInfo course={course} />
      <ErrorNote error={settings.error} />
      {settings.isLoading && <p className="text-muted-foreground">{t("app.loading")}</p>}
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
        {refused && <Alert variant="warning" role="alert">{t("archive.refused")} {(archive.error as ApiError).message}</Alert>}
        <ErrorNote error={refused ? null : archive.error} />
        {course.status === "archived"
          ? <p className="text-sm text-muted-foreground">{t("archive.done")}</p>
          : <Button type="button" variant="outline" onClick={() => archive.mutate()} disabled={archive.isPending}>{t("archive.button")}</Button>}
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
            {save.isSuccess && <p role="status" className="text-sm text-emerald-700 dark:text-emerald-300">{t("settings.saved")}</p>}
            <Button type="submit" disabled={save.isPending}>{t("settings.save")}</Button>
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
  const save = useMutation({
    mutationFn: () => api.saveCourseSettings(course.id, values, initial.version),
    onSuccess: (fresh) => {
      qc.setQueryData(["settings", course.id], fresh);
      qc.invalidateQueries({ queryKey: ["courses"] });
    },
  });
  const conflict = save.error instanceof ApiError && save.error.status === 409;
  function submit(e: FormEvent) {
    e.preventDefault();
    save.mutate();
  }
  return (
    <Card>
      <CardHeader><CardTitle>{t("settings.title")}</CardTitle><CardDescription>{t("settings.hint")}</CardDescription></CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4">
          <div className="grid gap-1.5 sm:max-w-sm">
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
          <div className="grid gap-1.5 sm:max-w-sm">
            <Label htmlFor="set-routing">{t("settings.routing")}</Label>
            <Select id="set-routing" value={values.routing_preference ?? "default"}
                    onChange={(e) => setValues({ ...values, routing_preference: e.target.value as CourseValues["routing_preference"] })}>
              <option value="default">{t("settings.routingDefault")}</option>
              <option value="prefer_local">{t("settings.routingLocal")}</option>
              <option value="prefer_cloud">{t("settings.routingCloud")}</option>
            </Select>
          </div>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-0.5 accent-primary" checked={values.show_routing_progress ?? true}
                   onChange={(e) => setValues({ ...values, show_routing_progress: e.target.checked })} />
            <span className="font-medium">{t("settings.showProgress")}</span>
          </label>
          {conflict && <Alert variant="warning">{t("settings.conflict")}</Alert>}
          <ErrorNote error={conflict ? null : save.error} />
          {save.isSuccess && <p role="status" className="text-sm text-emerald-700 dark:text-emerald-300">{t("settings.saved")}</p>}
          <Button type="submit" disabled={save.isPending}>{save.isPending ? t("settings.saving") : t("settings.save")}</Button>
        </form>
      </CardContent>
    </Card>
  );
}
