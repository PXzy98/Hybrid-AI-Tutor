import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api, type Course } from "@/api/endpoints";
import { ErrorNote } from "@/components/common";
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
  const [moduleId, setModuleId] = useState<number | undefined>(undefined);
  const summary = useQuery({ queryKey: ["class-summary", course.id, moduleId ?? null], queryFn: () => api.classSummary(course.id, moduleId) });
  const data = summary.data;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{t("overview.title")}</h2>
          <p className="text-sm text-muted-foreground">{t("overview.intro")}</p>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="overview-module">{t("overview.module")}</Label>
          <Select id="overview-module" value={moduleId ?? ""} onChange={(e) => setModuleId(e.target.value ? Number(e.target.value) : undefined)}>
            <option value="">{t("nav.wholeCourse")}</option>
            {modules.data?.map((m) => <option key={m.id} value={m.id}>{m.title}</option>)}
          </Select>
        </div>
      </div>
      <ErrorNote error={summary.error} />
      <InsightsCard course={course} />
      {summary.isLoading && <p className="text-muted-foreground">{t("app.loading")}</p>}
      {data?.suppressed && <Alert variant="info" role="status">{t("overview.suppressed", { n: data.min_group })}</Alert>}
      {data && !data.suppressed && (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Card><CardHeader><CardDescription>{t("overview.students")}</CardDescription><CardTitle className="text-3xl">{data.students ?? 0}</CardTitle></CardHeader></Card>
            <Card><CardHeader><CardDescription>{t("overview.kcs")}</CardDescription><CardTitle className="text-3xl">{data.kcs?.length ?? 0}</CardTitle></CardHeader></Card>
            <Card><CardHeader><CardDescription>{t("overview.misconceptions")}</CardDescription><CardTitle className="text-3xl">{data.misconceptions?.length ?? 0}</CardTitle></CardHeader></Card>
          </div>
          <Card>
            <CardHeader><CardTitle>{t("overview.bands")}</CardTitle><CardDescription>{t("overview.bandsHint")}</CardDescription></CardHeader>
            <CardContent>
              <Table>
                <TableHeader><TableRow>
                  <TableHead>{t("overview.kc")}</TableHead>
                  {BANDS.map((b) => <TableHead key={b}>{t(`band.${b}` as MessageKey)}</TableHead>)}
                </TableRow></TableHeader>
                <TableBody>
                  {data.kcs?.map((k) => (
                    <TableRow key={k.kc_id}>
                      <TableCell className="font-medium">{k.name}</TableCell>
                      {BANDS.map((b) => <TableCell key={b} className="tabular-nums">{b in k.counts ? (k.counts[b] ?? t("overview.hidden")) : "—"}</TableCell>)}
                    </TableRow>
                  ))}
                  {!data.kcs?.length && <TableRow><TableCell colSpan={5} className="text-muted-foreground">{t("overview.noKcs")}</TableCell></TableRow>}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>{t("overview.misconceptions")}</CardTitle></CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm">
                {data.misconceptions?.map((m) => (
                  <li key={m.misconception_id} className="flex justify-between gap-3">
                    <span>{m.statement}</span><span className="tabular-nums text-muted-foreground">{t("overview.studentsN", { n: m.students })}</span>
                  </li>
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
        {data?.suppressed && <Alert variant="info" role="status">{t("insights.suppressed", { n: data.min_group })}</Alert>}
        {data && !data.suppressed && (
          <div className="grid gap-6 md:grid-cols-2">
            <div>
              <h3 className="mb-2 text-sm font-medium">{t("insights.kcs")}</h3>
              <ul className="space-y-1 text-sm">
                {data.kc_question_counts.map((k) => (
                  <li key={k.label} className="flex justify-between gap-3"><span>{k.name ?? k.label}</span><span className="tabular-nums text-muted-foreground">{k.count}</span></li>
                ))}
                {data.kc_question_counts.length === 0 && <li className="text-muted-foreground">{t("insights.none")}</li>}
              </ul>
            </div>
            <div>
              <h3 className="mb-2 text-sm font-medium">{t("insights.misconceptions")}</h3>
              <ul className="space-y-1 text-sm">
                {data.misconception_counts.map((k) => (
                  <li key={k.label} className="flex justify-between gap-3"><span>{k.name ?? k.label}</span><span className="tabular-nums text-muted-foreground">{k.count}</span></li>
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
