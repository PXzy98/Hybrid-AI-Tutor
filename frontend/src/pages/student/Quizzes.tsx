import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ListChecks, XCircle } from "lucide-react";
import { useState, type FormEvent } from "react";

import { api, type Course, type OwnAttempt, type StudentQuiz } from "@/api/endpoints";
import { choiceRow, EmptyState, ErrorNote, Loading, PageHeader } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/i18n";
import { useFormat } from "@/lib/format";

/** Student quizzes: open quizzes are answered once; the result and the explanations show right after. */
export default function Quizzes({ course }: { course: Course }) {
  const { t } = useI18n();
  const quizzes = useQuery({ queryKey: ["quizzes", course.id], queryFn: () => api.studentQuizzes(course.id) });
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader title={t("quiz.title")} description={t("quiz.studentIntro")} />
      <ErrorNote error={quizzes.error} />
      {quizzes.isLoading && <Loading variant="list" />}
      {quizzes.data?.length === 0 && <EmptyState icon={ListChecks} title={t("empty.quizzes.title")}>{t("quiz.studentNone")}</EmptyState>}
      <ul className="space-y-4">
        {quizzes.data?.map((q) => <li key={q.id}><QuizCard course={course} quiz={q} /></li>)}
      </ul>
    </div>
  );
}

function QuizCard({ course, quiz }: { course: Course; quiz: StudentQuiz }) {
  const { t } = useI18n();
  const fmt = useFormat();
  const qc = useQueryClient();
  const questions = quiz.questions ?? [];
  const [answers, setAnswers] = useState<(number | null)[]>(() => questions.map(() => null));
  const submit = useMutation({
    mutationFn: () => api.attemptQuiz(course.id, quiz.id, answers as number[]),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["quizzes", course.id] }),
  });
  const attempt: OwnAttempt | null | undefined = submit.data ?? quiz.attempt;
  const complete = answers.length > 0 && answers.every((a) => a !== null);
  function send(e: FormEvent) {
    e.preventDefault();
    if (complete) submit.mutate();
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">{quiz.title}
          <Badge variant="outline">{t(`quiz.kind.${quiz.kind}`)}</Badge>
          <Badge variant={quiz.open ? "success" : "secondary"}>{t(quiz.open ? "quiz.open" : "quiz.notOpen")}</Badge>
        </CardTitle>
        <CardDescription>
          {quiz.opens_at && `${t("quiz.opens")} ${fmt.dateTime(quiz.opens_at)}`}
          {quiz.closes_at && ` · ${t("quiz.closes")} ${fmt.dateTime(quiz.closes_at)}`}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {attempt ? (
          <div role="status" className="space-y-3">
            <p className="font-medium">{t("quiz.score", { })}: {attempt.score} / {attempt.total}</p>
            <ol className="space-y-3">
              {attempt.results.map((r, i) => {
                const q = questions[i];
                return (
                  <li key={i} className={`rounded-lg border p-3 text-sm ${r.correct ? "border-success-border bg-success-soft/50" : "border-destructive/30 bg-destructive-soft/50"}`}>
                    <p className="flex items-center gap-2 font-medium">
                      {r.correct ? <CheckCircle2 aria-hidden className="size-4 text-success" /> : <XCircle aria-hidden className="size-4 text-destructive" />}
                      {t("quiz.questionN", { n: i + 1 })}: {t(r.correct ? "quiz.correct" : "quiz.incorrect")}
                    </p>
                    {q && <p className="mt-1">{q.stem}</p>}
                    <p className="text-muted-foreground">
                      {t("quiz.yourAnswer")}: {q ? (q.options ?? [])[r.chosen] : r.chosen + 1} · {t("quiz.rightAnswer")}: {q ? (q.options ?? [])[r.answer] : r.answer + 1}
                    </p>
                    {r.explanation && <p className="mt-1">{r.explanation}</p>}
                  </li>
                );
              })}
            </ol>
          </div>
        ) : quiz.open ? (
          <form onSubmit={send} className="space-y-4" aria-label={quiz.title}>
            {questions.map((q, i) => (
              <div key={i} className="border-t pt-4 first:border-0 first:pt-0">
                <fieldset className="space-y-2">
                  <legend className="text-sm"><span className="font-medium">{i + 1}.</span> {q.stem}</legend>
                  {(q.options ?? []).map((o, j) => (
                    <label key={j} className={choiceRow(answers[i] === j)}>
                      <input type="radio" name={`quiz-${quiz.id}-${i}`} className="mt-0.5 accent-primary" checked={answers[i] === j}
                             onChange={() => setAnswers(answers.map((a, k) => (k === i ? j : a)))} />
                      <span>{o}</span>
                    </label>
                  ))}
                </fieldset>
              </div>
            ))}
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
              <span>{t("quiz.onceHint")}</span>
              <span className="tabular-nums">{t("quiz.answeredN", { n: answers.filter((a) => a !== null).length, m: answers.length })}</span>
            </div>
            <ErrorNote error={submit.error} />
            <Button loading={submit.isPending} type="submit" disabled={!complete || submit.isPending}>{submit.isPending ? t("check.busy") : t("quiz.submit")}</Button>
          </form>
        ) : <p className="text-sm text-muted-foreground">{t("quiz.notAvailable")}</p>}
      </CardContent>
    </Card>
  );
}
