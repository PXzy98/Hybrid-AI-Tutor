import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { EyeOff } from "lucide-react";
import { useState, type FormEvent } from "react";

import { ApiError } from "@/api/client";
import { api, type Course, type Plan } from "@/api/endpoints";
import Band from "@/components/Band";
import { ErrorNote } from "@/components/common";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useI18n } from "@/i18n";

const GOALS = ["basic", "intermediate", "advanced"] as const;

/** Per-student progress. The list comes from the members; one student's overview is only requested when the
 * instructor opens it (each view is audited), and an answer of 404 is shown as "not visible". */
export default function Students({ course }: { course: Course }) {
  const { t } = useI18n();
  const members = useQuery({ queryKey: ["members", course.id], queryFn: () => api.members(course.id) });
  const [open, setOpen] = useState<string | null>(null);
  const students = members.data?.filter((m) => m.role === "student") ?? [];
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">{t("students.title")}</h2>
        <p className="text-sm text-muted-foreground">{t("students.intro")}</p>
      </div>
      <ErrorNote error={members.error} />
      {members.isLoading && <p className="text-muted-foreground">{t("app.loading")}</p>}
      {members.data && (
        <Card>
          <CardContent>
            <Table>
              <TableHeader><TableRow>
                <TableHead>{t("members.name")}</TableHead><TableHead>{t("members.email")}</TableHead>
                <TableHead>{t("members.status")}</TableHead><TableHead>{t("students.visibility")}</TableHead><TableHead><span className="sr-only">{t("students.actions")}</span></TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {students.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell className="font-medium">{m.display_name ?? "—"}</TableCell>
                    <TableCell>{m.email ?? "—"}</TableCell>
                    <TableCell><Badge variant={m.status === "active" ? "success" : "secondary"}>{t(`members.status.${m.status}`)}</Badge></TableCell>
                    <TableCell>
                      {m.student_id && m.status === "active" && (
                        <Badge variant={m.visible_to_instructor ? "warning" : "secondary"}>
                          {t(m.visible_to_instructor ? "students.visible" : "students.hidden")}
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {m.student_id && m.status === "active" && m.visible_to_instructor ? (
                        <Button type="button" size="sm" variant="outline" aria-label={t("students.viewFor", { name: m.display_name ?? "" })}
                                onClick={() => setOpen(open === m.student_id ? null : m.student_id ?? null)}>
                          {open === m.student_id ? t("students.hide") : t("students.view")}
                        </Button>
                      ) : <span className="text-xs text-muted-foreground">{t(m.status === "active" ? "students.notShared" : "students.notJoined")}</span>}
                    </TableCell>
                  </TableRow>
                ))}
                {students.length === 0 && <TableRow><TableCell colSpan={5} className="text-muted-foreground">{t("students.none")}</TableCell></TableRow>}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
      {open && <StudentDetail key={open} course={course} studentId={open}
                              name={students.find((s) => s.student_id === open)?.display_name ?? ""} />}
    </div>
  );
}

function StudentDetail({ course, studentId, name }: { course: Course; studentId: string; name: string }) {
  const { t } = useI18n();
  const overview = useQuery({
    queryKey: ["overview", course.id, studentId],
    queryFn: () => api.studentOverview(course.id, studentId),
    retry: false,
    // every open asks the backend again: it is the visibility and audit boundary, so nothing is cached
    staleTime: 0, gcTime: 0, refetchOnMount: "always", refetchOnWindowFocus: false,
  });
  // after a refusal, data from an earlier answer is never shown
  const shown = overview.isError ? undefined : overview.data;
  const notVisible = overview.error instanceof ApiError && overview.error.status === 404;
  return (
    <Card aria-label={t("students.detail", { name })}>
      <CardHeader>
        <CardTitle>{name || t("students.detailFallback")}</CardTitle>
        {shown && <CardDescription>{t("students.since", { date: new Date(shown.visible_since).toLocaleDateString() })}</CardDescription>}
      </CardHeader>
      <CardContent className="space-y-4">
        {overview.isLoading && <p className="text-muted-foreground">{t("app.loading")}</p>}
        {notVisible && (
          <Alert variant="info" role="status" className="flex gap-3">
            <EyeOff aria-hidden className="mt-0.5 size-4 shrink-0" />
            <div>
              <p className="font-medium">{t("students.notVisible")}</p>
              <p>{t("students.notVisibleWhy", { mode: course.visibility_mode })}</p>
            </div>
          </Alert>
        )}
        {!notVisible && <ErrorNote error={overview.error} />}
        {shown && (
          <>
            <div className="grid gap-3 text-sm sm:grid-cols-3">
              <p><span className="text-muted-foreground">{t("students.checks")}</span> <strong>{shown.checks_answered ?? 0}</strong></p>
              <p><span className="text-muted-foreground">{t("students.misconceptions")}</span> <strong>{shown.open_misconceptions ?? 0}</strong></p>
              <p><span className="text-muted-foreground">{t("students.lastActive")}</span> <strong>{shown.last_active ? new Date(shown.last_active).toLocaleDateString() : "—"}</strong></p>
            </div>
            <ul className="space-y-1.5">
              {shown.kcs?.map((k) => (
                <li key={k.kc_code} className="flex items-center justify-between gap-3 text-sm">
                  <span>{k.kc_code}</span><Band band={k.level} />
                </li>
              ))}
              {!shown.kcs?.length && <li className="text-sm text-muted-foreground">{t("students.noKcs")}</li>}
            </ul>
            <PlanEditor course={course} studentId={studentId} />
          </>
        )}
      </CardContent>
    </Card>
  );
}

/** The learning plan of one visible student. The student sees it on the "My progress" tab. */
export function PlanEditor({ course, studentId }: { course: Course; studentId: string }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const kcs = useQuery({ queryKey: ["kcs", course.id], queryFn: () => api.kcs(course.id) });
  const plan = useQuery({
    queryKey: ["plan", course.id, studentId], queryFn: () => api.studentPlan(course.id, studentId), retry: false,
    staleTime: 0, gcTime: 0, refetchOnMount: "always", refetchOnWindowFocus: false,
  });
  if (plan.isLoading || kcs.isLoading) return <p className="text-muted-foreground">{t("app.loading")}</p>;
  const missing = plan.error instanceof ApiError && plan.error.status === 404;
  return (
    <>
      {!missing && <ErrorNote error={plan.error} />}
      <PlanForm initial={plan.isError ? undefined : plan.data} codes={(kcs.data ?? []).filter((k) => k.status === "active")}
                courseId={course.id} studentId={studentId} onSaved={(p) => qc.setQueryData(["plan", course.id, studentId], p)} />
    </>
  );
}

function PlanForm({ initial, codes, courseId, studentId, onSaved }: {
  initial?: Plan; codes: { code: string; name: string }[]; courseId: number; studentId: string; onSaved: (p: Plan) => void;
}) {
  const { t } = useI18n();
  const [focus, setFocus] = useState<string[]>(initial?.focus_kcs ?? []);
  const [goal, setGoal] = useState<Plan["goal"]>(initial?.goal ?? "intermediate");
  const [notes, setNotes] = useState(initial?.notes ?? "");
  const save = useMutation({
    mutationFn: () => api.savePlan(courseId, studentId, { focus_kcs: focus, goal, notes }),
    onSuccess: onSaved,
  });
  const toggle = (code: string) => setFocus(focus.includes(code) ? focus.filter((c) => c !== code) : [...focus, code]);
  function submit(e: FormEvent) {
    e.preventDefault();
    save.mutate();
  }
  return (
    <form onSubmit={submit} className="space-y-4 border-t pt-4" aria-label={t("plan.editor")}>
      <h3 className="font-medium">{t("plan.editor")}</h3>
      <p className="text-sm text-muted-foreground">{t("plan.editorHint")}</p>
      <div className="grid gap-1.5 sm:max-w-xs">
        <Label htmlFor="plan-goal">{t("plan.goal")}</Label>
        <Select id="plan-goal" value={goal} onChange={(e) => setGoal(e.target.value as Plan["goal"])}>
          {GOALS.map((g) => <option key={g} value={g}>{t(`band.${g}`)}</option>)}
        </Select>
      </div>
      <fieldset className="space-y-1.5">
        <legend className="mb-1 text-sm font-medium">{t("plan.focus")}</legend>
        {codes.map((k) => (
          <label key={k.code} className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="accent-primary" checked={focus.includes(k.code)} onChange={() => toggle(k.code)} />
            <span><span className="font-medium">{k.code}</span> {k.name}</span>
          </label>
        ))}
        {codes.length === 0 && <p className="text-sm text-muted-foreground">{t("plan.noKcs")}</p>}
      </fieldset>
      <div className="grid gap-1.5">
        <Label htmlFor="plan-notes">{t("plan.notes")}</Label>
        <Textarea id="plan-notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
      </div>
      <ErrorNote error={save.error} />
      {save.isSuccess && <p role="status" className="text-sm text-emerald-700 dark:text-emerald-300">{t("plan.saved")}</p>}
      <Button type="submit" disabled={save.isPending}>{save.isPending ? t("settings.saving") : t("plan.save")}</Button>
    </form>
  );
}
