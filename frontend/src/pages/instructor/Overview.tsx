import { useQuery } from "@tanstack/react-query";
import { BookOpen, Lightbulb, Users } from "lucide-react";
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
