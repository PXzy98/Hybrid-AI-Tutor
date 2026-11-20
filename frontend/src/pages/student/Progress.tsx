import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChartNoAxesColumn, Eye, EyeOff, Lightbulb, Sparkles } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { api, type Course, type CourseProfile, type VisibilityAction } from "@/api/endpoints";
import Band from "@/components/Band";
import { EmptyState, ErrorNote, Loading, PageHeader, StatusText } from "@/components/common";
import { Alert } from "@/components/ui/alert";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { tEnglish, useI18n } from "@/i18n";
import { useFormat } from "@/lib/format";
import type { MessageKey } from "@/i18n/en";

/** "My progress": what the tutor knows about the student in this course (bands only), what the instructor
 * can see, and the choices that control it. Shows what the API returns and decides nothing itself. */
export default function Progress({ course }: { course: Course }) {
  const { t } = useI18n();
  const profile = useQuery({ queryKey: ["profile", course.id], queryFn: () => api.profile(course.id) });
  if (profile.isLoading) return <Loading variant="cards" />;
  if (profile.isError || !profile.data) return <ErrorNote error={profile.error ?? new Error(t("me.loadError"))} />;
  const data = profile.data;
  const explanations = data.preferences?.sequencing && data.preferences.detail
    ? t("me.explanations", { sequencing: t(`me.pref.${data.preferences.sequencing}` as MessageKey), detail: t(`me.pref.${data.preferences.detail}` as MessageKey) })
    : undefined;
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
      <div className="min-w-0 space-y-4">
        <PageHeader title={t("me.title")} description={data.personalized ? explanations : undefined} />
        {!data.personalized ? (
          <EmptyState icon={Sparkles} title={t("empty.profile.title")}
                      action={<Button asChild><Link to={`/courses/${course.id}/start`}>{t("me.personalize")}</Link></Button>}>
            {t("me.noProfile")}
          </EmptyState>
        ) : (
          <>
            {data.modules?.length === 0 && <EmptyState icon={ChartNoAxesColumn} title={t("empty.progress.title")}>{t("me.empty")}</EmptyState>}
            {data.modules?.map((m) => (
              <section key={m.module_id} aria-label={m.title}>
                <Card>
                  <CardHeader><CardTitle>{m.title}</CardTitle></CardHeader>
                  <CardContent className="space-y-4">
                    <ul className="divide-y">
                      {m.kcs.map((k) => (
                        <li key={k.kc_id} className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5 py-2.5 text-sm first:pt-0 last:pb-0">
                          <span className="min-w-0">{k.name}</span>
                          <span className="flex items-center gap-2">
                            {k.band === "basic" && (
                              // V8: a weak topic gets another explanation; the request goes to the chat in router state, not the URL
                              <Button asChild size="sm" variant="outline">
                                <Link to={`/courses/${course.id}/chat?module=${m.module_id}`} state={{ ask: tEnglish("loop.ask", { kc: k.name }) }}
                                      aria-label={t("loop.explainFor", { kc: k.name })}>{t("loop.explain")}</Link>
                              </Button>
                            )}
                            <Band band={k.band} />
                          </span>
                        </li>
                      ))}
                    </ul>
                    {!!m.misconceptions?.length && (
                      <div className="rounded-lg border border-info-border bg-info-soft p-3 text-sm">
                        <p className="mb-2 flex items-center gap-1.5 font-medium"><Lightbulb aria-hidden className="size-4 text-info" />{t("me.working")}</p>
                        <ul className="space-y-2">
                          {m.misconceptions.map((x) => (
                            <li key={`${x.kc_id}:${x.statement}`}>
                              <p>{t("me.mixup")} {x.statement}</p>
                              <p className="text-muted-foreground">{t("me.true")} {x.correction}</p>
                              <p className="text-xs text-muted-foreground">{t(`me.source.${x.status}` as MessageKey)}</p>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </section>
            ))}
            {course.individual_view && <PlanCard plan={data.plan} />}
          </>
        )}
      </div>
      <div className="min-w-0 space-y-4">
        <VisibilityCard course={course} profile={data} />
        {data.personalized && <AnswerInstruction />}
        <DeleteData course={course} />
      </div>
    </div>
  );
}

function PlanCard({ plan }: { plan: CourseProfile["plan"] }) {
  const { t } = useI18n();
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("plan.title")}</CardTitle>
        <CardDescription>{t("plan.studentHint")}</CardDescription>
      </CardHeader>
      <CardContent>
        {!plan ? <p className="text-sm text-muted-foreground">{t("plan.none")}</p> : (
          <dl className="grid gap-3 text-sm">
            <div><dt className="mb-1 text-xs text-muted-foreground">{t("plan.goal")}</dt><dd><Band band={plan.goal} /></dd></div>
            <div><dt className="mb-1 text-xs text-muted-foreground">{t("plan.focus")}</dt>
              <dd>{plan.focus_kcs.length ? plan.focus_kcs.join(", ") : "—"}</dd></div>
            {plan.notes && <div><dt className="mb-1 text-xs text-muted-foreground">{t("plan.notes")}</dt><dd className="whitespace-pre-wrap">{plan.notes}</dd></div>}
          </dl>
        )}
      </CardContent>
    </Card>
  );
}

function VisibilityCard({ course, profile }: { course: Course; profile: CourseProfile }) {
  const { t } = useI18n();
  const fmt = useFormat();
  const qc = useQueryClient();
  const v = profile.visibility;
  const change = useMutation({
    mutationFn: (action: VisibilityAction) => api.setVisibility(course.id, action),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["profile", course.id] }),
  });
  return (
    <Card aria-label={t("vis.title")}>
      <CardHeader>
        <CardTitle>{t("vis.title")}</CardTitle>
        <CardDescription>{t(v.mode === "A" ? "vis.modeA" : "vis.modeB")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="flex items-center gap-3 rounded-lg border bg-muted/40 p-3">
          <span aria-hidden className={`flex size-9 shrink-0 items-center justify-center rounded-full ${v.visible_to_instructor ? "bg-info-soft text-info" : "bg-success-soft text-success"}`}>
            {v.visible_to_instructor ? <Eye className="size-4" /> : <EyeOff className="size-4" />}
          </span>
          <Badge variant={v.visible_to_instructor ? "info" : "success"} className="min-w-0 shrink whitespace-normal text-left">
            {t(v.visible_to_instructor ? "vis.visible" : "vis.hidden")}
          </Badge>
        </div>
        {v.mode === "B" && (
          <>
            {v.visible_since && <p className="text-muted-foreground">{t("vis.since", { date: fmt.date(v.visible_since) })}</p>}
            {!v.acknowledged && !v.opted_out && (
              <>
                <Alert variant="warning" icon>{t("vis.ackText")}</Alert>
                <Button type="button" className="w-full" onClick={() => change.mutate("acknowledge")} loading={change.isPending}>{t("vis.acknowledge")}</Button>
              </>
            )}
            {v.acknowledged && !v.opted_out && (
              <Button type="button" variant="outline" className="w-full" onClick={() => change.mutate("opt_out")} loading={change.isPending}>{t("vis.optOut")}</Button>
            )}
            {v.opted_out && (
              <>
                <p>{t("vis.optedOut")}</p>
                <Button type="button" variant="outline" className="w-full" onClick={() => change.mutate("opt_in")} loading={change.isPending}>{t("vis.optIn")}</Button>
              </>
            )}
          </>
        )}
        <ErrorNote error={change.error} />
      </CardContent>
    </Card>
  );
}

/** V15: how the student wants answers presented, in their own words. Only the course's own model reads it,
 *  after the instructor's rules; nobody else sees it. Needs consent (shown only with a profile). */
function AnswerInstruction() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const saved = useQuery({ queryKey: ["answer-instruction"], queryFn: api.answerInstruction });
  const [text, setText] = useState<string | null>(null);
  const value = text ?? saved.data?.text ?? "";
  const save = useMutation({
    mutationFn: () => api.saveAnswerInstruction(value),
    onSuccess: (fresh) => { qc.setQueryData(["answer-instruction"], fresh); setText(null); },
  });
  const dirty = text !== null && text !== (saved.data?.text ?? "");
  return (
    <Card aria-label={t("own.title")}>
      <CardHeader><CardTitle>{t("own.title")}</CardTitle><CardDescription>{t("own.hint")}</CardDescription></CardHeader>
      <CardContent className="space-y-3 text-sm">
        <Label htmlFor="own-text" className="sr-only">{t("own.title")}</Label>
        <Textarea id="own-text" value={value} maxLength={300} placeholder={t("own.placeholder")}
                  onChange={(e) => { setText(e.target.value); save.reset(); }} />
        <p className="text-xs text-muted-foreground">{t("own.privacy")}</p>
        <ErrorNote error={save.error ?? saved.error} />
        {save.isSuccess && !dirty && <StatusText>{t("own.saved")}</StatusText>}
        <Button type="button" size="sm" loading={save.isPending} disabled={!dirty || save.isPending} onClick={() => save.mutate()}>{t("settings.save")}</Button>
      </CardContent>
    </Card>
  );
}

/** Deletes the student's own learning data in this course, after a confirmation that says what goes. */
function DeleteData({ course }: { course: Course }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const remove = useMutation({
    mutationFn: () => api.deleteLearningData(course.id),
    onSuccess: async () => {
      setOpen(false);
      await qc.invalidateQueries({ queryKey: ["profile", course.id] });
      qc.invalidateQueries({ queryKey: ["conversations", course.id] });
    },
  });
  return (
    <Card className="border-destructive/30">
      <CardHeader><CardTitle>{t("del.title")}</CardTitle><CardDescription>{t("del.hint")}</CardDescription></CardHeader>
      <CardContent className="space-y-3">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild><Button type="button" variant="destructive" className="h-auto min-h-9 max-w-full py-2 whitespace-normal">{t("del.button")}</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t("del.confirmTitle")}</DialogTitle>
              <DialogDescription>{t("del.confirmBody")}</DialogDescription>
            </DialogHeader>
            <ErrorNote error={remove.error} />
            <DialogFooter>
              <DialogClose asChild><Button type="button" variant="outline">{t("end.cancel")}</Button></DialogClose>
              <Button type="button" variant="destructive" loading={remove.isPending} onClick={() => remove.mutate()}>{t("del.confirm")}</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        {remove.isSuccess && <StatusText>{t("del.done")}</StatusText>}
      </CardContent>
    </Card>
  );
}
