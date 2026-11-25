import { useQuery } from "@tanstack/react-query";
import { BookOpen, Cpu, Lightbulb, MessageSquare, UserCheck, Users } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { api, type Course } from "@/api/endpoints";
import BandBar from "@/components/BandBar";
import { ErrorNote, Loading, PageHeader, StatCard } from "@/components/common";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { tEnglish, useI18n } from "@/i18n";
import { useFormat } from "@/lib/format";
import type { MessageKey } from "@/i18n/en";

const BANDS = ["basic", "intermediate", "advanced", "mastered"];

/** A count of students: a dash for nobody (or a band the API does not list), "hidden" for a group too small to show. */
const countCell = (n: number | null | undefined, listed: boolean, hidden: string) => (!listed || n === 0 ? "—" : n ?? hidden);

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
      <PageHeader title={t("overview.title")} description={t("overview.intro")} />
      <ErrorNote error={summary.error} />
      <UsageCard course={course} />
      <WeakTopicsCard course={course} />
      <InsightsCard course={course} />
      {/* the module picker sits with the topic levels it changes, and only when there is a module to pick */}
      {!!modules.data?.length && (
        <div className="grid max-w-sm gap-1.5">
          <Label htmlFor="overview-module">{t("overview.module")}</Label>
          <Select id="overview-module" value={moduleId ?? ""} onChange={(e) => setChosen(Number(e.target.value))}>
            {modules.data.map((m) => <option key={m.id} value={m.id}>{m.title}</option>)}
          </Select>
        </div>
      )}
      {summary.isLoading && <Loading variant="cards" />}
      {data?.suppressed && <Alert variant="info" role="status" icon>{t("overview.suppressed", { n: data.min_group })}</Alert>}
      {data && !data.suppressed && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
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
                  <TableHead className="hidden w-40 md:table-cell" aria-hidden />
                </TableRow></TableHeader>
                <TableBody>
                  {data.kcs?.map((k) => (
                    <TableRow key={k.kc_id}>
                      <TableCell className="font-medium">{k.name}</TableCell>
                      {BANDS.map((b) => <TableCell key={b} className="tabular-nums">{countCell(k.counts[b], b in k.counts, t("overview.hidden"))}</TableCell>)}
                      <TableCell className="hidden md:table-cell"><BandBar counts={k.counts} bands={BANDS} /></TableCell>
                    </TableRow>
                  ))}
                  {!data.kcs?.length && <TableRow><TableCell colSpan={6} className="text-muted-foreground">{t("overview.noKcs")}</TableCell></TableRow>}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>{t("overview.misconceptions")}</CardTitle><CardDescription>{t("overview.misconceptionsHint")}</CardDescription></CardHeader>
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
  // a week or module nobody asked about is not a row: the lists stay short and say so when they are empty
  const busyModules = modules.filter((m) => m.questions !== 0);
  const quietModules = modules.filter((m) => m.questions === 0);
  const busyWeeks = (data?.weeks ?? []).filter((w) => w.questions !== 0);
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
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <StatCard label={t("usage.enrolled")} value={data.students_enrolled} icon={Users} />
              <StatCard label={t("usage.active7d")} value={show(data.active_students_7d)} icon={UserCheck} />
              <StatCard label={t("usage.questions7d")} value={show(data.questions_7d)} icon={MessageSquare} />
              {/* no question yet: nothing to hide, nothing to show */}
              <StatCard label={t("usage.local")} value={data.questions_total === 0 ? "—" : pct(data.local_share) ?? hidden} icon={Cpu} />
            </div>
            <div className="grid gap-6 md:grid-cols-2">
              <div>
                <h3 className="mb-2 text-sm font-medium">{t("usage.perWeek")}</h3>
                <ul className="space-y-1.5 text-sm">
                  {busyWeeks.map((w) => (
                    <RankedRow key={w.week_start} label={t("usage.weekOf", { date: fmt.day(w.week_start) })}
                               count={w.questions == null ? hidden
                                 // a student count below the minimum group is not sent: never write it as 0
                                 : w.students == null ? t("usage.questionsOnly", { q: w.questions })
                                   : t("usage.questionsStudents", { q: w.questions, s: w.students })}
                               share={(w.questions ?? 0) / weekMax} />
                  ))}
                </ul>
                {busyWeeks.length === 0 && <p className="text-sm text-muted-foreground">{t("usage.noActivity")}</p>}
              </div>
              <div>
                <h3 className="mb-2 text-sm font-medium">{t("usage.perModule")}</h3>
                <ul className="space-y-1.5 text-sm">
                  {busyModules.map((m) => (
                    <RankedRow key={m.module_id ?? "course"} label={m.module_id === null ? t("usage.wholeCourse") : m.title}
                               count={show(m.questions)} share={(m.questions ?? 0) / most} />
                  ))}
                </ul>
                {busyModules.length === 0 && <p className="text-sm text-muted-foreground">{t("usage.noActivity")}</p>}
                {quietModules.length > 0 && (
                  <details className="mt-2 text-sm">
                    <summary className="cursor-pointer text-muted-foreground">{t("usage.quietModules", { n: quietModules.length })}</summary>
                    <ul className="mt-1 list-disc space-y-0.5 pl-5">{quietModules.map((m) => <li key={m.module_id}>{m.title}</li>)}</ul>
                  </details>
                )}
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

/** V8: topics the class finds hard in quizzes (each with at least the minimum group of students), with a way
 *  to draft extra material on one. Counts and shares only. */
function WeakTopicsCard({ course }: { course: Course }) {
  const { t } = useI18n();
  const weak = useQuery({ queryKey: ["weak-topics", course.id], queryFn: () => api.weakTopics(course.id) });
  const data = weak.data;
  return (
    <Card aria-label={t("loop.title")}>
      <CardHeader><CardTitle>{t("loop.title")}</CardTitle><CardDescription>{t("loop.hint", { n: data?.min_group ?? 5 })}</CardDescription></CardHeader>
      <CardContent>
        <ErrorNote error={weak.error} />
        {data && data.topics.length === 0 && <p className="text-sm text-muted-foreground">{t("loop.none")}</p>}
        <ul className="divide-y">
          {data?.topics.map((w) => (
            <li key={w.kc_code} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
              <span className="min-w-0"><span className="font-medium">{w.name}</span>{" "}
                <span className="text-muted-foreground">{t("loop.rate", { pct: Math.round(w.correct_rate * 100), n: w.students })}</span></span>
              <Button asChild size="sm" variant="outline">
                <Link to={`/courses/${course.id}/ai`} state={{ draft: { request: tEnglish("loop.draftRequest", { kc: w.name }), moduleId: w.module_id } }}
                      aria-label={t("loop.draftFor", { kc: w.name })}>{t("loop.draft")}</Link>
              </Button>
            </li>
          ))}
        </ul>
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
              <h3 className="text-sm font-medium">{t("insights.kcs")}</h3>
              <p className="mb-2 text-xs text-muted-foreground">{t("insights.kcsCaption", { n: data.min_group })}</p>
              <ul className="space-y-1.5 text-sm">
                {data.kc_question_counts.map((k) => (
                  <RankedRow key={k.label} label={k.name ?? k.label} count={k.count}
                             share={k.count / Math.max(1, ...data.kc_question_counts.map((x) => x.count))} />
                ))}
                {data.kc_question_counts.length === 0 && <li className="text-muted-foreground">{t("insights.kcsNone", { n: data.min_group })}</li>}
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
    // narrow: the count goes below the label instead of squeezing it to one word per line
    <li className="relative flex flex-wrap justify-between gap-x-3 overflow-hidden rounded-md px-2.5 py-1.5">
      <span aria-hidden className="absolute inset-y-0 left-0 rounded-md bg-primary-soft" style={{ width: `${Math.round(share * 100)}%` }} />
      <span className="relative min-w-0">{label}</span>
      <span className="relative shrink-0 tabular-nums text-muted-foreground">{count}</span>
    </li>
  );
}
