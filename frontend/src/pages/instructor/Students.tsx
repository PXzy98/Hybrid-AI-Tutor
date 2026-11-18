import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { EyeOff, Users } from "lucide-react";
import { useState, type FormEvent } from "react";

import { ApiError } from "@/api/client";
import { api, type Course, type Plan } from "@/api/endpoints";
import Band from "@/components/Band";
import { EmptyState, ErrorNote, Loading, PageHeader, StatusText } from "@/components/common";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useI18n } from "@/i18n";
import { useFormat } from "@/lib/format";
import type { MessageKey } from "@/i18n/en";

const GOALS = ["basic", "intermediate", "advanced"] as const;

/** Per-student progress. The list comes from the members; one student's overview is only requested when the
 * instructor opens it (each view is audited), and an answer of 404 is shown as "not visible". */
export default function Students({ course }: { course: Course }) {
  const { t } = useI18n();
  const members = useQuery({ queryKey: ["members", course.id], queryFn: () => api.members(course.id) });
  const [open, setOpen] = useState<string | null>(null);
  const students = members.data?.filter((m) => m.role === "student") ?? [];
  return (
    <div className="space-y-6">
      <PageHeader title={t("students.title")} description={t("students.intro")} />
      <ErrorNote error={members.error} />
      {members.isLoading && <Loading variant="table" />}
      {members.data && students.length === 0 && <EmptyState icon={Users} title={t("empty.students.title")}>{t("students.none")}</EmptyState>}
      {members.data && students.length > 0 && (
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
                        <Badge variant={m.visible_to_instructor ? "info" : "secondary"}>
                          {t(m.visible_to_instructor ? "students.visible" : "students.hidden")}
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {m.student_id && m.status === "active" && m.visible_to_instructor ? (
                        <Button type="button" size="sm" variant="outline" aria-label={t("students.viewFor", { name: m.display_name ?? "" })}
                                onClick={() => setOpen(m.student_id ?? null)}>
                          {t("students.view")}
                        </Button>
                      ) : <span className="text-xs text-muted-foreground">{t(m.status === "active" ? "students.notShared" : "students.notJoined")}</span>}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
      )}
      {/* the detail opens beside the list, so the list stays in place; closing it unmounts the detail, so the next
          open asks the backend again (one audited overview request per open) */}
      <Sheet open={open !== null} onOpenChange={(o) => { if (!o) setOpen(null); }}>
        {open && (
          <SheetContent side="right" aria-describedby={undefined} className="overflow-y-auto">
            <StudentDetail key={open} course={course} studentId={open}
                           name={students.find((s) => s.student_id === open)?.display_name ?? ""} />
          </SheetContent>
        )}
      </Sheet>
    </div>
  );
}

function StudentDetail({ course, studentId, name }: { course: Course; studentId: string; name: string }) {
  const { t } = useI18n();
  const fmt = useFormat();
  const overview = useQuery({
    queryKey: ["overview", course.id, studentId],
    queryFn: () => api.studentOverview(course.id, studentId),
    retry: false,
    // every open asks the backend again: it is the visibility and audit boundary, so nothing is cached
    staleTime: 0, gcTime: 0, refetchOnMount: "always", refetchOnWindowFocus: false,
  });
  const kcs = useQuery({ queryKey: ["kcs", course.id], queryFn: () => api.kcs(course.id) });
  const kcName = new Map((kcs.data ?? []).map((k) => [k.code, k.name]));
  // after a refusal, data from an earlier answer is never shown
  const shown = overview.isError ? undefined : overview.data;
  const notVisible = overview.error instanceof ApiError && overview.error.status === 404;
  return (
    <section aria-label={t("students.detail", { name })} className="space-y-5 p-6">
      <div className="space-y-1 pr-8">
        <SheetTitle className="text-base font-semibold">{name || t("students.detailFallback")}</SheetTitle>
        {shown && <p className="text-sm text-muted-foreground">{t("students.since", { date: fmt.date(shown.visible_since) })}</p>}
      </div>
        {overview.isLoading && <Loading variant="table" />}
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
              <p className="rounded-lg border p-3"><span className="block text-xs text-muted-foreground">{t("students.checks")}</span> <strong className="text-lg tabular-nums">{shown.checks_answered ?? 0}</strong></p>
              <p className="rounded-lg border p-3"><span className="block text-xs text-muted-foreground">{t("students.misconceptions")}</span> <strong className="text-lg tabular-nums">{shown.open_misconceptions ?? 0}</strong></p>
              <p className="rounded-lg border p-3"><span className="block text-xs text-muted-foreground">{t("students.lastActive")}</span> <strong className="text-lg">{shown.last_active ? fmt.date(shown.last_active) : "—"}</strong></p>
            </div>
            <p className="text-sm">
              <span className="text-muted-foreground">{t("students.preferences")}</span>{" "}
              <strong>{shown.preferences
                ? t("students.preferencesValue", {
                    sequencing: t(`me.pref.${shown.preferences.sequencing}` as MessageKey),
                    detail: t(`me.pref.${shown.preferences.detail}` as MessageKey),
                  })
                : t("students.preferencesNone")}</strong>
            </p>
            <ul className="divide-y rounded-lg border px-3">
              {shown.kcs?.map((k) => (
                <li key={k.kc_code} className="flex items-center justify-between gap-3 py-2 text-sm">
                  <span className="min-w-0">{kcName.get(k.kc_code) ?? k.kc_code} <span className="text-xs text-muted-foreground">{k.kc_code}</span></span>
                  <Band band={k.level} />
                </li>
              ))}
              {!shown.kcs?.length && <li className="py-2 text-sm text-muted-foreground">{t("students.noKcs")}</li>}
            </ul>
            <PlanEditor course={course} studentId={studentId} />
          </>
        )}
    </section>
  );
}

/** The learning plan of one visible student. The student sees it on the "My progress" tab. */
export function PlanEditor({ course, studentId }: { course: Course; studentId: string }) {
  const qc = useQueryClient();
  const kcs = useQuery({ queryKey: ["kcs", course.id], queryFn: () => api.kcs(course.id) });
  const plan = useQuery({
    queryKey: ["plan", course.id, studentId], queryFn: () => api.studentPlan(course.id, studentId), retry: false,
    staleTime: 0, gcTime: 0, refetchOnMount: "always", refetchOnWindowFocus: false,
  });
  if (plan.isLoading || kcs.isLoading) return <Loading variant="table" />;
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
          <label key={k.code} className="flex items-center gap-2 rounded-md px-1 py-0.5 text-sm hover:bg-accent">
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
      {save.isSuccess && <StatusText>{t("plan.saved")}</StatusText>}
      <Button loading={save.isPending} type="submit" disabled={save.isPending}>{save.isPending ? t("settings.saving") : t("plan.save")}</Button>
    </form>
  );
}
