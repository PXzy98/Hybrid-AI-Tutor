import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api, type Course, type Survey as SurveyData, type SurveyAnswers } from "@/api/endpoints";
import { choiceRow, ErrorNote, Loading, PageHeader, StatusText } from "@/components/common";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useI18n } from "@/i18n";
import type { MessageKey } from "@/i18n/en";
import { fromLocalInput, toLocalInput } from "./instructor/Quizzes";

const ITEMS = ["helpfulness", "material_relevance", "clarity", "source_confidence", "learning_effect"] as const;

/** The end-of-term survey: the instructor sets the window and reads averages, the student answers once. */
export default function Survey({ course, student }: { course: Course; student: boolean }) {
  const { t } = useI18n();
  const survey = useQuery({ queryKey: ["survey", course.id], queryFn: () => api.survey(course.id) });
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader title={t("survey.title")} description={t(student ? "survey.studentIntro" : "survey.intro")} />
      <ErrorNote error={survey.error} />
      {survey.isLoading && <Loading variant="form" />}
      {survey.data && (student ? <StudentSurvey course={course} survey={survey.data} /> : <InstructorSurvey course={course} survey={survey.data} />)}
    </div>
  );
}

function WindowBadge({ survey }: { survey: SurveyData }) {
  const { t } = useI18n();
  if (!survey.opens_at) return <Badge variant="secondary">{t("survey.notSet")}</Badge>;
  return <Badge variant={survey.open ? "success" : "secondary"}>{t(survey.open ? "survey.open" : "survey.closed")}</Badge>;
}

function InstructorSurvey({ course, survey }: { course: Course; survey: SurveyData }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [opens, setOpens] = useState(toLocalInput(survey.opens_at));
  const [closes, setCloses] = useState(toLocalInput(survey.closes_at));
  const save = useMutation({
    mutationFn: () => api.setSurveyWindow(course.id, fromLocalInput(opens) as string, fromLocalInput(closes) as string),
    onSuccess: (fresh) => qc.setQueryData(["survey", course.id], fresh),
  });
  const r = survey.results;
  return (
    <>
      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2">{t("survey.window")} <WindowBadge survey={survey} /></CardTitle><CardDescription>{t("survey.windowHint")}</CardDescription></CardHeader>
        <CardContent>
          <form className="flex flex-wrap items-end gap-4" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
            <div className="grid gap-1.5"><Label htmlFor="sv-opens">{t("quiz.opens")}</Label>
              <Input id="sv-opens" type="datetime-local" value={opens} onChange={(e) => setOpens(e.target.value)} required /></div>
            <div className="grid gap-1.5"><Label htmlFor="sv-closes">{t("quiz.closes")}</Label>
              <Input id="sv-closes" type="datetime-local" value={closes} onChange={(e) => setCloses(e.target.value)} required /></div>
            <Button type="submit" loading={save.isPending}>{t("settings.save")}</Button>
          </form>
          <div className="mt-3"><ErrorNote error={save.error} /></div>
        </CardContent>
      </Card>
      {r && (
        <Card>
          <CardHeader><CardTitle>{t("survey.results")}</CardTitle><CardDescription>{t("survey.responsesN", { n: r.responses })}</CardDescription></CardHeader>
          <CardContent>
            {!r.sufficient_sample || !r.means ? (
              <Alert variant="info" role="status" icon>{t("survey.notEnough", { n: r.min_group_size })}</Alert>
            ) : (
              <Table>
                <TableHeader><TableRow><TableHead>{t("survey.item")}</TableHead><TableHead>{t("survey.mean")}</TableHead></TableRow></TableHeader>
                <TableBody>{ITEMS.map((k) => (
                  <TableRow key={k}><TableCell>{t(`survey.q.${k}` as MessageKey)}</TableCell><TableCell className="tabular-nums">{r.means?.[k]?.toFixed(2) ?? "—"}</TableCell></TableRow>
                ))}</TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}
    </>
  );
}

function StudentSurvey({ course, survey }: { course: Course; survey: SurveyData }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [ratings, setRatings] = useState<Partial<SurveyAnswers>>({});
  const send = useMutation({
    mutationFn: () => api.answerSurvey(course.id, ratings as SurveyAnswers),
    onSuccess: (fresh) => qc.setQueryData(["survey", course.id], fresh),
  });
  if (survey.answered) return <StatusText>{t("survey.thanks")}</StatusText>;
  if (!survey.open) return <Alert variant="info" role="status" icon>{t("survey.notOpenStudent")}</Alert>;
  const complete = ITEMS.every((k) => ratings[k]);
  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2">{t("survey.title")} <WindowBadge survey={survey} /></CardTitle><CardDescription>{t("survey.anonymous")}</CardDescription></CardHeader>
      <CardContent>
        <form className="space-y-5" onSubmit={(e: FormEvent) => { e.preventDefault(); if (complete) send.mutate(); }} aria-label={t("survey.title")}>
          {ITEMS.map((k) => (
            <div key={k} className="border-t pt-5 first:border-0 first:pt-0">
              <fieldset role="radiogroup" aria-label={t(`survey.q.${k}` as MessageKey)} className="space-y-2">
                <legend className="text-sm font-medium">{t(`survey.q.${k}` as MessageKey)}</legend>
                <div className="max-w-md space-y-1.5">
                  <div className="grid grid-cols-5 gap-2 text-sm">
                    {[1, 2, 3, 4, 5].map((n) => (
                      <label key={n} className={`${choiceRow(ratings[k] === n)} items-center justify-center px-2 py-1.5 tabular-nums`}>
                        <input type="radio" name={`sv-${k}`} value={n} className="accent-primary" checked={ratings[k] === n}
                               onChange={() => setRatings({ ...ratings, [k]: n })} />{n}
                      </label>
                    ))}
                  </div>
                  <div className="flex justify-between gap-3 text-xs text-muted-foreground">
                    <span>{t("survey.low")}</span><span className="text-right">{t("survey.high")}</span>
                  </div>
                </div>
              </fieldset>
            </div>
          ))}
          <ErrorNote error={send.error} />
          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" loading={send.isPending} disabled={!complete}>{t("survey.submit")}</Button>
            <span className="text-xs tabular-nums text-muted-foreground">{t("quiz.answeredN", { n: ITEMS.filter((x) => ratings[x]).length, m: ITEMS.length })}</span>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
