import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, XCircle } from "lucide-react";
import { useState, type FormEvent } from "react";

import { api, type Course, type OwnAttempt, type StudentQuiz } from "@/api/endpoints";
import { ErrorNote } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/i18n";

/** Student quizzes: open quizzes are answered once; the result and the explanations show right after. */
export default function Quizzes({ course }: { course: Course }) {
  const { t } = useI18n();
  const quizzes = useQuery({ queryKey: ["quizzes", course.id], queryFn: () => api.studentQuizzes(course.id) });
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">{t("quiz.title")}</h2>
        <p className="text-sm text-muted-foreground">{t("quiz.studentIntro")}</p>
      </div>
      <ErrorNote error={quizzes.error} />
      {quizzes.isLoading && <p className="text-muted-foreground">{t("app.loading")}</p>}
      {quizzes.data?.length === 0 && <p className="text-muted-foreground">{t("quiz.studentNone")}</p>}
      <ul className="space-y-4">
        {quizzes.data?.map((q) => <li key={q.id}><QuizCard course={course} quiz={q} /></li>)}
      </ul>
    </div>
  );
}

function QuizCard({ course, quiz }: { course: Course; quiz: StudentQuiz }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [answers, setAnswers] = useState<(number | null)[]>(() => quiz.questions.map(() => null));
  // the questions are only sent before the first answer, so they are kept to show next to the result
  const [asked] = useState(quiz.questions);
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
          {quiz.opens_at && `${t("quiz.opens")} ${new Date(quiz.opens_at).toLocaleString()}`}
          {quiz.closes_at && ` · ${t("quiz.closes")} ${new Date(quiz.closes_at).toLocaleString()}`}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {attempt ? (
          <div role="status" className="space-y-3">
            <p className="font-medium">{t("quiz.score", { })}: {attempt.score} / {attempt.total}</p>
            <ol className="space-y-3">
              {attempt.results.map((r, i) => {
                const q = asked[i];
                return (
                  <li key={i} className="rounded-md border p-3 text-sm">
                    <p className="flex items-center gap-2 font-medium">
                      {r.correct ? <CheckCircle2 aria-hidden className="size-4 text-emerald-600" /> : <XCircle aria-hidden className="size-4 text-rose-600" />}
                      {t("quiz.questionN", { n: i + 1 })}: {t(r.correct ? "quiz.correct" : "quiz.incorrect")}
                    </p>
                    {q && <p className="mt-1">{q.stem}</p>}
                    <p className="text-muted-foreground">
                      {t("quiz.yourAnswer")}: {q ? q.options[r.chosen] : r.chosen + 1} · {t("quiz.rightAnswer")}: {q ? q.options[r.answer] : r.answer + 1}
                    </p>
                    {r.explanation && <p className="mt-1">{r.explanation}</p>}
                  </li>
                );
              })}
            </ol>
          </div>
        ) : quiz.open ? (
          <form onSubmit={send} className="space-y-4" aria-label={quiz.title}>
            {quiz.questions.map((q, i) => (
              <fieldset key={i} className="space-y-2">
                <legend className="text-sm"><span className="font-medium">{i + 1}.</span> {q.stem}</legend>
                {q.options.map((o, j) => (
                  <label key={j} className="flex cursor-pointer items-start gap-2 rounded-md border bg-card px-3 py-2 text-sm">
                    <input type="radio" name={`quiz-${quiz.id}-${i}`} className="mt-0.5 accent-primary" checked={answers[i] === j}
                           onChange={() => setAnswers(answers.map((a, k) => (k === i ? j : a)))} />
                    <span>{o}</span>
                  </label>
                ))}
              </fieldset>
            ))}
            <p className="text-xs text-muted-foreground">{t("quiz.onceHint")}</p>
            <ErrorNote error={submit.error} />
            <Button type="submit" disabled={!complete || submit.isPending}>{submit.isPending ? t("check.busy") : t("quiz.submit")}</Button>
          </form>
        ) : <p className="text-sm text-muted-foreground">{t("quiz.notAvailable")}</p>}
      </CardContent>
    </Card>
  );
}
