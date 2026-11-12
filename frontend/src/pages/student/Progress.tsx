import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, EyeOff } from "lucide-react";
import { Link } from "react-router-dom";

import { api, type Course, type CourseProfile, type VisibilityAction } from "@/api/endpoints";
import Band from "@/components/Band";
import { ErrorNote } from "@/components/common";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/i18n";
import type { MessageKey } from "@/i18n/en";

/** "My progress": what the tutor knows about the student in this course (bands only), what the instructor
 * can see, and the choices that control it. Shows what the API returns and decides nothing itself. */
export default function Progress({ course }: { course: Course }) {
  const { t } = useI18n();
  const profile = useQuery({ queryKey: ["profile", course.id], queryFn: () => api.profile(course.id) });
  if (profile.isLoading) return <p className="text-muted-foreground">{t("app.loading")}</p>;
  if (profile.isError || !profile.data) return <ErrorNote error={profile.error ?? new Error(t("me.loadError"))} />;
  const data = profile.data;
  return (
    <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
      <div className="space-y-4">
        {!data.personalized ? (
          <Card>
            <CardHeader><CardTitle>{t("me.title")}</CardTitle><CardDescription>{t("me.noProfile")}</CardDescription></CardHeader>
            <CardContent><Button asChild><Link to={`/courses/${course.id}/start`}>{t("me.personalize")}</Link></Button></CardContent>
          </Card>
        ) : (
          <>
            <Card>
              <CardHeader>
                <CardTitle>{t("me.title")}</CardTitle>
                {data.preferences?.sequencing && data.preferences.detail && (
                  <CardDescription>
                    {t("me.explanations", { sequencing: t(`me.pref.${data.preferences.sequencing}` as MessageKey), detail: t(`me.pref.${data.preferences.detail}` as MessageKey) })}
                  </CardDescription>
                )}
              </CardHeader>
              <CardContent className="space-y-5">
                {data.modules?.length === 0 && <p className="text-sm text-muted-foreground">{t("me.empty")}</p>}
                {data.modules?.map((m) => (
                  <section key={m.module_id} aria-label={m.title} className="space-y-2">
                    <h3 className="font-medium">{m.title}</h3>
                    <ul className="space-y-1.5">
                      {m.kcs.map((k) => (
                        <li key={k.kc_id} className="flex items-center justify-between gap-3 text-sm">
                          <span>{k.name}</span><Band band={k.band} />
                        </li>
                      ))}
                    </ul>
                    {!!m.misconceptions?.length && (
                      <div className="rounded-md border bg-muted/40 p-3 text-sm">
                        <p className="mb-1 font-medium">{t("me.working")}</p>
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
                  </section>
                ))}
              </CardContent>
            </Card>
            <PlanCard plan={data.plan} />
          </>
        )}
      </div>
      <VisibilityCard course={course} profile={data} />
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
          <dl className="space-y-2 text-sm">
            <div><dt className="font-medium">{t("plan.goal")}</dt><dd><Band band={plan.goal} /></dd></div>
            <div><dt className="font-medium">{t("plan.focus")}</dt>
              <dd>{plan.focus_kcs.length ? plan.focus_kcs.join(", ") : "—"}</dd></div>
            {plan.notes && <div><dt className="font-medium">{t("plan.notes")}</dt><dd className="whitespace-pre-wrap">{plan.notes}</dd></div>}
          </dl>
        )}
      </CardContent>
    </Card>
  );
}

function VisibilityCard({ course, profile }: { course: Course; profile: CourseProfile }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const v = profile.visibility;
  const change = useMutation({
    mutationFn: (action: VisibilityAction) => api.setVisibility(course.id, action),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["profile", course.id] }),
  });
  return (
    <Card aria-label={t("vis.title")}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">{v.visible_to_instructor ? <Eye aria-hidden className="size-4" /> : <EyeOff aria-hidden className="size-4" />}{t("vis.title")}</CardTitle>
        <CardDescription>{t(v.mode === "A" ? "vis.modeA" : "vis.modeB")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <Badge variant={v.visible_to_instructor ? "warning" : "success"}>
          {t(v.visible_to_instructor ? "vis.visible" : "vis.hidden")}
        </Badge>
        {v.mode === "B" && (
          <>
            {v.visible_since && <p className="text-muted-foreground">{t("vis.since", { date: new Date(v.visible_since).toLocaleDateString() })}</p>}
            {!v.acknowledged && !v.opted_out && (
              <>
                <Alert variant="warning">{t("vis.ackText")}</Alert>
                <Button type="button" onClick={() => change.mutate("acknowledge")} disabled={change.isPending}>{t("vis.acknowledge")}</Button>
              </>
            )}
            {v.acknowledged && !v.opted_out && (
              <Button type="button" variant="outline" onClick={() => change.mutate("opt_out")} disabled={change.isPending}>{t("vis.optOut")}</Button>
            )}
            {v.opted_out && (
              <>
                <p>{t("vis.optedOut")}</p>
                <Button type="button" variant="outline" onClick={() => change.mutate("opt_in")} disabled={change.isPending}>{t("vis.optIn")}</Button>
              </>
            )}
          </>
        )}
        <ErrorNote error={change.error} />
      </CardContent>
    </Card>
  );
}
