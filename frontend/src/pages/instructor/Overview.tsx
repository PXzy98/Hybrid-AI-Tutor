import { useQuery } from "@tanstack/react-query";
import { BookOpen, Cpu, Lightbulb, MessageSquare, UserCheck, Users } from "lucide-react";
import { useState, type ReactNode } from "react";

import { api, type Course } from "@/api/endpoints";
import BandBar from "@/components/BandBar";
import { ErrorNote, Loading, PageHeader, StatCard } from "@/components/common";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useI18n } from "@/i18n";
import { useFormat } from "@/lib/format";
import type { MessageKey } from "@/i18n/en";

const BANDS = ["basic", "intermediate", "advanced", "mastered"];

/** Class overview: aggregates per module. Small groups come back suppressed from the API and are shown as such. */
export default function Overview({ course }: { course: Course }) {
  const { t } = useI18n();
  const modules = useQuery({ queryKey: ["modules", course.id], queryFn: () => api.modules(course.id) });
  const [chosen, setChosen] = useState<number | undefined>(undefined);
  // the class summary is per module (the API needs module_id): the first module until another is chosen
  const moduleId = chosen ?? modules.data?.[0]?.id;
  const summary = useQuery({
    queryKey: ["class-summary", course.id, moduleId ?? null],
    queryFn: () => api.classSummary(course.id, moduleId as number),
    enabled: moduleId !== undefined,
  });
  const data = summary.data;
  return (
    <div className="space-y-6">
      <PageHeader title={t("overview.title")} description={t("overview.intro")} actions={
        <div className="grid gap-1.5">
          <Label htmlFor="overview-module">{t("overview.module")}</Label>
          <Select id="overview-module" value={moduleId ?? ""} onChange={(e) => setChosen(Number(e.target.value))}>
            {modules.data?.map((m) => <option key={m.id} value={m.id}>{m.title}</option>)}
          </Select>
        </div>
      } />
      <ErrorNote error={summary.error} />
      <UsageCard course={course} />
      <InsightsCard course={course} />
      {summary.isLoading && <Loading variant="cards" />}
      {data?.suppressed && <Alert variant="info" role="status" icon>{t("overview.suppressed", { n: data.min_group })}</Alert>}
      {data && !data.suppressed && (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard label={t("overview.students")} value={data.students ?? 0} icon={Users} />
            <StatCard label={t("overview.kcs")} value={data.kcs?.length ?? 0} icon={BookOpen} />
            <StatCard label={t("overview.misconceptions")} value={data.misconceptions?.length ?? 0} icon={Lightbulb} />
          </div>
          <Card>
            <CardHeader><CardTitle>{t("overview.bands")}</CardTitle><CardDescription>{t("overview.bandsHint")}</CardDescription></CardHeader>
            <CardContent>
              <Table>
                <TableHeader><TableRow>
                  <TableHead>{t("overview.kc")}</TableHead>
                  {BANDS.map((b) => <TableHead key={b}>{t(`band.${b}` as MessageKey)}</TableHead>)}
                  <TableHead className="hidden w-40 md:table-cell"><span className="sr-only">{t("overview.bands")}</span></TableHead>
                </TableRow></TableHeader>
                <TableBody>
                  {data.kcs?.map((k) => (
                    <TableRow key={k.kc_id}>
                      <TableCell className="font-medium">{k.name}</TableCell>
                      {BANDS.map((b) => <TableCell key={b} className="tabular-nums">{b in k.counts ? (k.counts[b] ?? t("overview.hidden")) : "—"}</TableCell>)}
                      <TableCell className="hidden md:table-cell"><BandBar counts={k.counts} bands={BANDS} /></TableCell>
                    </TableRow>
                  ))}
                  {!data.kcs?.length && <TableRow><TableCell colSpan={6} className="text-muted-foreground">{t("overview.noKcs")}</TableCell></TableRow>}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>{t("overview.misconceptions")}</CardTitle></CardHeader>
            <CardContent>
              <ul className="space-y-1.5 text-sm">
                {data.misconceptions?.map((m) => (
                  <RankedRow key={m.misconception_id} label={m.statement} count={t("overview.studentsN", { n: m.students })}
                             share={m.students / Math.max(1, ...(data.misconceptions ?? []).map((x) => x.students))} />
                ))}
                {!data.misconceptions?.length && <li className="text-muted-foreground">{t("overview.noMisconceptions")}</li>}
                {!!data.misconceptions_hidden && <li className="text-muted-foreground">{t("overview.moreHidden", { n: data.misconceptions_hidden })}</li>}
              </ul>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

const pct = (x: number | null | undefined) => (x == null ? null : `${Math.round(x * 100)}%`);

/** v5 V2: how many students use the tutor, questions per week and per module, quiz averages. Counts that fewer
 *  than the minimum group contributed come back as null and are shown as hidden. */
function UsageCard({ course }: { course: Course }) {
  const { t } = useI18n();
  const fmt = useFormat();
  const stats = useQuery({ queryKey: ["statistics", course.id], queryFn: () => api.courseStatistics(course.id) });
  const data = stats.data;
  const hidden = t("overview.hidden");
  const show = (n: number | null | undefined) => (n == null ? hidden : n);
  const modules = (data?.modules ?? []).filter((m) => m.module_id !== null || m.questions !== 0);
  const most = Math.max(1, ...modules.map((m) => m.questions ?? 0));
  const weekMax = Math.max(1, ...(data?.weeks ?? []).map((w) => w.questions ?? 0));
  return (
    <Card aria-label={t("usage.title")}>
      <CardHeader><CardTitle>{t("usage.title")}</CardTitle><CardDescription>{t("usage.hint", { n: data?.min_group ?? 5 })}</CardDescription></CardHeader>
      <CardContent className="space-y-6">
        <ErrorNote error={stats.error} />
        {stats.isLoading && <Loading variant="cards" />}
        {data && (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard label={t("usage.enrolled")} value={data.students_enrolled} icon={Users} />
              <StatCard label={t("usage.active7d")} value={show(data.active_students_7d)} icon={UserCheck} />
              <StatCard label={t("usage.questions7d")} value={show(data.questions_7d)} icon={MessageSquare} />
              <StatCard label={t("usage.local")} value={pct(data.local_share) ?? hidden} icon={Cpu} />
            </div>
            <div className="grid gap-6 md:grid-cols-2">
              <div>
                <h3 className="mb-2 text-sm font-medium">{t("usage.perWeek")}</h3>
                <ul className="space-y-1.5 text-sm">
                  {data.weeks.map((w) => (
                    <RankedRow key={w.week_start} label={t("usage.weekOf", { date: fmt.day(w.week_start) })}
                               count={w.questions == null ? hidden : t("usage.questionsStudents", { q: w.questions, s: w.students ?? 0 })}
                               share={(w.questions ?? 0) / weekMax} />
                  ))}
                </ul>
              </div>
              <div>
                <h3 className="mb-2 text-sm font-medium">{t("usage.perModule")}</h3>
                <ul className="space-y-1.5 text-sm">
                  {modules.map((m) => (
                    <RankedRow key={m.module_id ?? "course"} label={m.module_id === null ? t("usage.wholeCourse") : m.title}
                               count={show(m.questions)} share={(m.questions ?? 0) / most} />
                  ))}
                </ul>
              </div>
            </div>
            <div>
              <h3 className="mb-2 text-sm font-medium">{t("usage.quizzes")}</h3>
              {data.quizzes.length === 0 ? <p className="text-sm text-muted-foreground">{t("usage.noQuizzes")}</p> : (
                <Table>
                  <TableHeader><TableRow><TableHead>{t("usage.quiz")}</TableHead><TableHead>{t("usage.attempts")}</TableHead><TableHead>{t("usage.average")}</TableHead></TableRow></TableHeader>
                  <TableBody>{data.quizzes.map((q) => (
                    <TableRow key={q.quiz_id}><TableCell className="font-medium">{q.title}</TableCell>
                      <TableCell className="tabular-nums">{show(q.attempts)}</TableCell>
                      <TableCell className="tabular-nums">{pct(q.mean_score) ?? hidden}</TableCell></TableRow>
                  ))}</TableBody>
                </Table>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

/** Tier 3: which topics students asked about most and the most common misconceptions (counts only). */
function InsightsCard({ course }: { course: Course }) {
  const { t } = useI18n();
  const insights = useQuery({ queryKey: ["insights", course.id], queryFn: () => api.insights(course.id) });
  const data = insights.data;
  return (
    <Card aria-label={t("insights.title")}>
      <CardHeader><CardTitle>{t("insights.title")}</CardTitle><CardDescription>{t("insights.hint")}</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        <ErrorNote error={insights.error} />
        {data?.suppressed && <Alert variant="info" role="status" icon>{t("insights.suppressed", { n: data.min_group })}</Alert>}
        {data && !data.suppressed && (
          <div className="grid gap-6 md:grid-cols-2">
            <div>
              <h3 className="mb-2 text-sm font-medium">{t("insights.kcs")}</h3>
              <ul className="space-y-1.5 text-sm">
                {data.kc_question_counts.map((k) => (
                  <RankedRow key={k.label} label={k.name ?? k.label} count={k.count}
                             share={k.count / Math.max(1, ...data.kc_question_counts.map((x) => x.count))} />
                ))}
                {data.kc_question_counts.length === 0 && <li className="text-muted-foreground">{t("insights.none")}</li>}
              </ul>
            </div>
            <div>
              <h3 className="mb-2 text-sm font-medium">{t("insights.misconceptions")}</h3>
              <ul className="space-y-1.5 text-sm">
                {data.misconception_counts.map((k) => (
                  <RankedRow key={k.label} label={k.name ?? k.label} count={k.count}
                             share={k.count / Math.max(1, ...data.misconception_counts.map((x) => x.count))} />
                ))}
                {data.misconception_counts.length === 0 && <li className="text-muted-foreground">{t("insights.none")}</li>}
              </ul>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/** A ranked row: a thin bar behind the label shows the count relative to the largest one (decorative; the count is
 *  written out). */
function RankedRow({ label, count, share }: { label: string; count: ReactNode; share: number }) {
  return (
    <li className="relative flex justify-between gap-3 overflow-hidden rounded-md px-2.5 py-1.5">
      <span aria-hidden className="absolute inset-y-0 left-0 rounded-md bg-primary-soft" style={{ width: `${Math.round(share * 100)}%` }} />
      <span className="relative min-w-0">{label}</span>
      <span className="relative shrink-0 tabular-nums text-muted-foreground">{count}</span>
    </li>
  );
}
