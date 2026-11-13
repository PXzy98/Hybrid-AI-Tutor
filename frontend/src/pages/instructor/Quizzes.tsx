import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Sparkles, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import { api, type Course, type DraftBody, type Quiz, type QuizQuestion, type QuizResults } from "@/api/endpoints";
import { ErrorNote } from "@/components/common";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useI18n } from "@/i18n";

type View = { kind: "list" } | { kind: "edit"; id: number | null } | { kind: "results"; id: number };

/** ISO time to the value of a datetime-local input, and back. */
export const toLocalInput = (iso: string | null | undefined) => {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
};
export const fromLocalInput = (value: string) => (value ? new Date(value).toISOString() : null);

const unreviewed = (q: Quiz) => q.questions.filter((x) => !x.reviewed).length;

/** Instructor quizzes: list, editor (with the AI draft and its review gate) and results. */
export default function Quizzes({ course }: { course: Course }) {
  const [view, setView] = useState<View>({ kind: "list" });
  if (view.kind === "edit") return <QuizEditor course={course} id={view.id} onClose={() => setView({ kind: "list" })} onCreated={(id) => setView({ kind: "edit", id })} />;
  if (view.kind === "results") return <ResultsView course={course} id={view.id} onClose={() => setView({ kind: "list" })} />;
  return <QuizList course={course} onOpen={setView} />;
}

function QuizList({ course, onOpen }: { course: Course; onOpen: (v: View) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const quizzes = useQuery({ queryKey: ["quizzes", course.id], queryFn: () => api.quizzes(course.id) });
  const refresh = () => qc.invalidateQueries({ queryKey: ["quizzes", course.id] });
  const change = useMutation({
    mutationFn: (v: { id: number; status: "published" | "closed" }) => api.updateQuiz(course.id, v.id, { status: v.status }),
    onSuccess: refresh,
  });
  const remove = useMutation({ mutationFn: (id: number) => api.deleteQuiz(course.id, id), onSuccess: refresh });
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{t("quiz.title")}</h2>
          <p className="text-sm text-muted-foreground">{t("quiz.intro")}</p>
        </div>
        <Button type="button" onClick={() => onOpen({ kind: "edit", id: null })}><Plus aria-hidden />{t("quiz.new")}</Button>
      </div>
      <ErrorNote error={quizzes.error ?? change.error ?? remove.error} />
      {quizzes.isLoading && <p className="text-muted-foreground">{t("app.loading")}</p>}
      {quizzes.data?.length === 0 && <p className="text-muted-foreground">{t("quiz.none")}</p>}
      <ul className="space-y-3">
        {quizzes.data?.map((q) => {
          const pending = unreviewed(q);
          return (
            <li key={q.id}>
              <Card>
                <CardHeader>
                  <CardTitle className="flex flex-wrap items-center gap-2">{q.title}
                    <Badge variant="outline">{t(`quiz.kind.${q.kind}`)}</Badge>
                    <Badge variant={q.status === "published" ? "success" : "secondary"}>{t(`quiz.status.${q.status}`)}</Badge>
                    {pending > 0 && <Badge variant="warning">{t("quiz.unreviewedN", { n: pending })}</Badge>}
                  </CardTitle>
                  <CardDescription>
                    {t("quiz.questionsN", { n: q.questions.length })} · {t("quiz.attemptsN", { n: q.attempts })}
                    {q.opens_at && ` · ${t("quiz.opens")} ${new Date(q.opens_at).toLocaleString()}`}
                    {q.closes_at && ` · ${t("quiz.closes")} ${new Date(q.closes_at).toLocaleString()}`}
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex flex-wrap gap-2">
                  <Button type="button" size="sm" variant="outline" aria-label={t("quiz.editFor", { name: q.title })} onClick={() => onOpen({ kind: "edit", id: q.id })}>{t("quiz.edit")}</Button>
                  <Button type="button" size="sm" variant="outline" aria-label={t("quiz.resultsFor", { name: q.title })} onClick={() => onOpen({ kind: "results", id: q.id })}>{t("quiz.results")}</Button>
                  {q.status === "draft" && (
                    <Button type="button" size="sm" aria-label={t("quiz.publishFor", { name: q.title })} disabled={pending > 0 || q.questions.length === 0 || change.isPending}
                            onClick={() => change.mutate({ id: q.id, status: "published" })}>{t("quiz.publish")}</Button>
                  )}
                  {q.status === "published" && (
                    <Button type="button" size="sm" variant="outline" aria-label={t("quiz.closeFor", { name: q.title })} onClick={() => change.mutate({ id: q.id, status: "closed" })}>{t("quiz.close")}</Button>
                  )}
                  {q.attempts === 0 && (
                    <Button type="button" size="sm" variant="ghost" aria-label={t("quiz.deleteFor", { name: q.title })} onClick={() => remove.mutate(q.id)}><Trash2 aria-hidden /></Button>
                  )}
                </CardContent>
              </Card>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

const blankQuestion = (): QuizQuestion => ({ kind: "mcq", kc: null, stem: "", options: ["", "", "", ""], answer: 0, explanation: "", sources: [], reviewed: true });

function QuizEditor({ course, id, onClose, onCreated }: { course: Course; id: number | null; onClose: () => void; onCreated: (id: number) => void }) {
  const { t } = useI18n();
  const quizzes = useQuery({ queryKey: ["quizzes", course.id], queryFn: () => api.quizzes(course.id) });
  if (quizzes.isLoading) return <p className="text-muted-foreground">{t("app.loading")}</p>;
  const quiz = id === null ? undefined : quizzes.data?.find((q) => q.id === id);
  // a new form every time the server copy changes (after a save or after the AI draft arrives)
  return <EditorForm key={quiz ? `${quiz.id}:${quiz.updated_at}` : "new"} course={course} quiz={quiz} onClose={onClose} onCreated={onCreated} />;
}

function EditorForm({ course, quiz, onClose, onCreated }: { course: Course; quiz?: Quiz; onClose: () => void; onCreated: (id: number) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const modules = useQuery({ queryKey: ["modules", course.id], queryFn: () => api.modules(course.id) });
  const kcs = useQuery({ queryKey: ["kcs", course.id], queryFn: () => api.kcs(course.id) });
  const members = useQuery({ queryKey: ["members", course.id], queryFn: () => api.members(course.id) });
  const [title, setTitle] = useState(quiz?.title ?? "");
  const [kind, setKind] = useState<Quiz["kind"]>(quiz?.kind ?? "practice");
  const [moduleId, setModuleId] = useState<number | null>(quiz?.module_id ?? null);
  const [opens, setOpens] = useState(toLocalInput(quiz?.opens_at));
  const [closes, setCloses] = useState(toLocalInput(quiz?.closes_at));
  const [assigned, setAssigned] = useState<string[] | null>(quiz?.assigned_to ?? null);
  const [questions, setQuestions] = useState<QuizQuestion[]>((quiz?.questions ?? []).map((q) => ({ ...q, options: q.options ?? [] })));
  const locked = !!quiz && quiz.attempts > 0;
  const students = (members.data ?? []).filter((m) => m.role === "student" && m.student_id);
  const pending = questions.filter((q) => !q.reviewed).length;

  const save = useMutation({
    mutationFn: () => {
      const body = { title, kind, module_id: moduleId, opens_at: fromLocalInput(opens), closes_at: fromLocalInput(closes), assigned_to: assigned };
      return quiz
        ? api.updateQuiz(course.id, quiz.id, locked ? { ...body } : { ...body, questions })
        : api.createQuiz(course.id, { ...body, questions });
    },
    onSuccess: (saved) => {
      qc.invalidateQueries({ queryKey: ["quizzes", course.id] });
      if (!quiz) onCreated(saved.id);
    },
  });
  const setQuestion = (i: number, patch: Partial<QuizQuestion>) => setQuestions(questions.map((q, j) => (j === i ? { ...q, ...patch } : q)));
  function submit(e: FormEvent) {
    e.preventDefault();
    save.mutate();
  }

  return (
    <form onSubmit={submit} className="space-y-4" aria-label={t("quiz.editor")}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">{quiz ? t("quiz.editTitle") : t("quiz.new")}</h2>
        <Button type="button" variant="outline" onClick={onClose}>{t("quiz.back")}</Button>
      </div>
      {locked && <Alert variant="info">{t("quiz.locked")}</Alert>}
      <Card>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="grid gap-1.5 sm:col-span-2"><Label htmlFor="q-title">{t("course.title")}</Label>
            <Input id="q-title" value={title} onChange={(e) => setTitle(e.target.value)} required /></div>
          <div className="grid gap-1.5"><Label htmlFor="q-kind">{t("quiz.kind")}</Label>
            <Select id="q-kind" value={kind} onChange={(e) => setKind(e.target.value as Quiz["kind"])}>
              <option value="practice">{t("quiz.kind.practice")}</option><option value="final">{t("quiz.kind.final")}</option>
            </Select></div>
          <div className="grid gap-1.5"><Label htmlFor="q-module">{t("content.module")}</Label>
            <Select id="q-module" value={moduleId ?? ""} onChange={(e) => setModuleId(e.target.value ? Number(e.target.value) : null)}>
              <option value="">{t("nav.wholeCourse")}</option>
              {modules.data?.map((m) => <option key={m.id} value={m.id}>{m.title}</option>)}
            </Select></div>
          <div className="grid gap-1.5"><Label htmlFor="q-opens">{t("quiz.opens")}</Label>
            <Input id="q-opens" type="datetime-local" value={opens} onChange={(e) => setOpens(e.target.value)} /></div>
          <div className="grid gap-1.5"><Label htmlFor="q-closes">{t("quiz.closes")}</Label>
            <Input id="q-closes" type="datetime-local" value={closes} onChange={(e) => setCloses(e.target.value)} /></div>
          <fieldset className="sm:col-span-2 space-y-1.5">
            <legend className="mb-1 text-sm font-medium">{t("quiz.assignment")}</legend>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="accent-primary" checked={assigned === null} onChange={(e) => setAssigned(e.target.checked ? null : [])} />
              {t("quiz.allStudents")}
            </label>
            {assigned !== null && students.map((s) => (
              <label key={s.id} className="ml-5 flex items-center gap-2 text-sm">
                <input type="checkbox" className="accent-primary" checked={assigned.includes(s.student_id as string)}
                       onChange={() => setAssigned(assigned.includes(s.student_id as string) ? assigned.filter((x) => x !== s.student_id) : [...assigned, s.student_id as string])} />
                {s.display_name ?? s.email}
              </label>
            ))}
          </fieldset>
        </CardContent>
      </Card>

      <section className="space-y-3" aria-label={t("quiz.questions")}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-medium">{t("quiz.questions")}</h3>
          {pending > 0 && <Badge variant="warning">{t("quiz.unreviewedN", { n: pending })}</Badge>}
        </div>
        {pending > 0 && <Alert variant="warning" role="status">{t("quiz.reviewGate")}</Alert>}
        {questions.map((q, i) => (
          <Card key={i} aria-label={t("quiz.questionN", { n: i + 1 })}>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <strong>{t("quiz.questionN", { n: i + 1 })}</strong>
                <div className="flex items-center gap-2">
                  {!q.reviewed && <Badge variant="warning">{t("quiz.unreviewed")}</Badge>}
                  {!locked && <Button type="button" size="icon" variant="ghost" aria-label={t("quiz.removeQuestion", { n: i + 1 })} onClick={() => setQuestions(questions.filter((_, j) => j !== i))}><Trash2 aria-hidden /></Button>}
                </div>
              </div>
              <fieldset disabled={locked} className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="grid gap-1.5"><Label htmlFor={`qq-kind-${i}`}>{t("quiz.questionKind")}</Label>
                    <Select id={`qq-kind-${i}`} value={q.kind}
                            onChange={(e) => setQuestion(i, e.target.value === "true_false" ? { kind: "true_false", options: ["True", "False"], answer: 0 } : { kind: "mcq", options: ["", "", "", ""], answer: 0 })}>
                      <option value="mcq">{t("quiz.mcq")}</option><option value="true_false">{t("quiz.trueFalse")}</option>
                    </Select></div>
                  <div className="grid gap-1.5"><Label htmlFor={`qq-kc-${i}`}>{t("content.kc")}</Label>
                    <Select id={`qq-kc-${i}`} value={q.kc ?? ""} onChange={(e) => setQuestion(i, { kc: e.target.value || null })}>
                      <option value="">{t("quiz.noKc")}</option>
                      {kcs.data?.map((k) => <option key={k.id} value={k.code}>{k.code} {k.name}</option>)}
                    </Select></div>
                </div>
                <div className="grid gap-1.5"><Label htmlFor={`qq-stem-${i}`}>{t("content.stem")}</Label>
                  <Textarea id={`qq-stem-${i}`} value={q.stem} onChange={(e) => setQuestion(i, { stem: e.target.value })} required /></div>
                <div className="space-y-2">
                  <p className="text-sm font-medium">{t("quiz.options")}</p>
                  {(q.options ?? []).map((o, j) => (
                    <div key={j} className="flex items-center gap-2">
                      <input type="radio" name={`qq-answer-${i}`} className="accent-primary" checked={q.answer === j}
                             aria-label={t("quiz.correctOption", { n: j + 1 })} onChange={() => setQuestion(i, { answer: j })} />
                      {q.kind === "true_false" ? <span className="text-sm">{o}</span>
                        : <Input aria-label={t("quiz.optionN", { n: j + 1 })} value={o} required
                                 onChange={(e) => setQuestion(i, { options: (q.options ?? []).map((x, k) => (k === j ? e.target.value : x)) })} />}
                      {q.kind === "mcq" && (q.options ?? []).length > 2 && (
                        <Button type="button" size="icon" variant="ghost" aria-label={t("quiz.removeOption", { n: j + 1 })}
                                onClick={() => setQuestion(i, { options: (q.options ?? []).filter((_, k) => k !== j), answer: q.answer === j ? 0 : q.answer > j ? q.answer - 1 : q.answer })}><Trash2 aria-hidden /></Button>
                      )}
                    </div>
                  ))}
                  {q.kind === "mcq" && (q.options ?? []).length < 6 && (
                    <Button type="button" size="sm" variant="outline" onClick={() => setQuestion(i, { options: [...(q.options ?? []), ""] })}>{t("quiz.addOption")}</Button>
                  )}
                </div>
                <div className="grid gap-1.5"><Label htmlFor={`qq-expl-${i}`}>{t("content.explanation")}</Label>
                  <Textarea id={`qq-expl-${i}`} value={q.explanation ?? ""} onChange={(e) => setQuestion(i, { explanation: e.target.value })} /></div>
                {!!q.sources?.length && <p className="text-xs text-muted-foreground">{t("quiz.fromMaterial", { files: q.sources.join(", ") })}</p>}
              </fieldset>
            </CardContent>
          </Card>
        ))}
        {!locked && <Button type="button" variant="outline" onClick={() => setQuestions([...questions, blankQuestion()])}><Plus aria-hidden />{t("quiz.addQuestion")}</Button>}
      </section>

      <ErrorNote error={save.error} />
      {save.isSuccess && <p role="status" className="text-sm text-emerald-700 dark:text-emerald-300">{t("settings.saved")}</p>}
      <div className="flex flex-wrap gap-3">
        <Button type="submit" disabled={save.isPending}>{save.isPending ? t("settings.saving") : t("quiz.save")}</Button>
      </div>
      {quiz && quiz.status === "draft" && !locked && <AiDraft course={course} quiz={quiz} />}
    </form>
  );
}

/** "Draft with AI": starts the job and polls it; the new questions arrive unreviewed. */
function AiDraft({ course, quiz }: { course: Course; quiz: Quiz }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [count, setCount] = useState(5);
  const [kinds, setKinds] = useState<DraftBody["kinds"]>(["mcq", "true_false"]);
  const [jobId, setJobId] = useState<number | null>(null);
  const start = useMutation({ mutationFn: () => api.draftQuiz(course.id, quiz.id, { count, kinds }), onSuccess: (d) => setJobId(d.job_id) });
  const job = useQuery({
    queryKey: ["job", course.id, jobId],
    queryFn: async () => {
      const j = await api.job(course.id, jobId as number);
      if (j.status === "done") qc.invalidateQueries({ queryKey: ["quizzes", course.id] });
      return j;
    },
    enabled: jobId !== null,
    refetchInterval: (q) => (q.state.data && (q.state.data.status === "done" || q.state.data.status === "failed") ? false : 1500),
  });
  const running = jobId !== null && job.data?.status !== "done" && job.data?.status !== "failed";
  const toggle = (k: "mcq" | "true_false") => {
    const next = kinds?.includes(k) ? kinds.filter((x) => x !== k) : [...(kinds ?? []), k];
    if (next.length) setKinds(next);
  };
  return (
    <Card aria-label={t("quiz.ai")}>
      <CardHeader><CardTitle className="flex items-center gap-2"><Sparkles aria-hidden className="size-4" />{t("quiz.ai")}</CardTitle><CardDescription>{t("quiz.aiHint")}</CardDescription></CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-end gap-4">
          <div className="grid gap-1.5"><Label htmlFor="ai-count">{t("quiz.aiCount")}</Label>
            <Input id="ai-count" type="number" min={1} max={20} className="w-24" value={count} onChange={(e) => setCount(Number(e.target.value))} /></div>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-primary" checked={!!kinds?.includes("mcq")} onChange={() => toggle("mcq")} />{t("quiz.mcq")}</label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-primary" checked={!!kinds?.includes("true_false")} onChange={() => toggle("true_false")} />{t("quiz.trueFalse")}</label>
          <Button type="button" onClick={() => start.mutate()} disabled={start.isPending || running}>{t("quiz.aiStart")}</Button>
        </div>
        <ErrorNote error={start.error ?? job.error} />
        {running && <p role="status" className="text-sm text-muted-foreground">{t("quiz.aiRunning")}</p>}
        {job.data?.status === "done" && <p role="status" className="text-sm text-emerald-700 dark:text-emerald-300">{t("quiz.aiDone")}</p>}
        {job.data?.status === "failed" && <Alert variant="destructive" role="alert">{t("quiz.aiFailed")}</Alert>}
      </CardContent>
    </Card>
  );
}

function ResultsView({ course, id, onClose }: { course: Course; id: number; onClose: () => void }) {
  const { t } = useI18n();
  const results = useQuery({ queryKey: ["quiz-results", course.id, id], queryFn: () => api.quizResults(course.id, id) });
  const members = useQuery({ queryKey: ["members", course.id], queryFn: () => api.members(course.id) });
  const name = (sid: string) => members.data?.find((m) => m.student_id === sid)?.display_name ?? sid;
  const r: QuizResults | undefined = results.data;
  const prePost = r?.pre_post as { students?: number; pre_mean?: number; post_mean?: number } | null | undefined;
  const pct = (x: number | null | undefined) => (x == null ? "—" : `${Math.round(x * 100)}%`);
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">{t("quiz.resultsTitle")}</h2>
        <Button type="button" variant="outline" onClick={onClose}>{t("quiz.back")}</Button>
      </div>
      <ErrorNote error={results.error} />
      {results.isLoading && <p className="text-muted-foreground">{t("app.loading")}</p>}
      {r && (
        <>
          <p className="text-sm text-muted-foreground">{t("quiz.attemptsN", { n: r.attempts })}</p>
          {!r.sufficient_sample ? (
            <Alert variant="info" role="status">{t("quiz.notEnough", { n: r.min_group_size })}</Alert>
          ) : (
            <>
              <Card><CardHeader><CardDescription>{t("quiz.meanScore")}</CardDescription><CardTitle className="text-3xl">{pct(r.mean_score)}</CardTitle></CardHeader></Card>
              <Card>
                <CardHeader><CardTitle>{t("quiz.perQuestion")}</CardTitle></CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader><TableRow><TableHead>{t("quiz.question")}</TableHead><TableHead>KC</TableHead><TableHead>{t("quiz.correctRate")}</TableHead></TableRow></TableHeader>
                    <TableBody>{(r.questions ?? []).map((q) => (
                      <TableRow key={q.position}><TableCell>{q.position + 1}</TableCell><TableCell>{q.kc ?? "—"}</TableCell><TableCell className="tabular-nums">{pct(q.correct_rate)}</TableCell></TableRow>
                    ))}</TableBody>
                  </Table>
                </CardContent>
              </Card>
              {prePost && (
                <Card>
                  <CardHeader><CardTitle>{t("quiz.prePost")}</CardTitle><CardDescription>{t("quiz.prePostHint", { n: prePost.students ?? 0 })}</CardDescription></CardHeader>
                  <CardContent className="grid gap-3 text-sm sm:grid-cols-2">
                    <p><span className="text-muted-foreground">{t("quiz.pre")}</span> <strong>{pct(prePost.pre_mean)}</strong></p>
                    <p><span className="text-muted-foreground">{t("quiz.post")}</span> <strong>{pct(prePost.post_mean)}</strong></p>
                  </CardContent>
                </Card>
              )}
            </>
          )}
          <Card>
            <CardHeader><CardTitle>{t("quiz.students")}</CardTitle><CardDescription>{t("quiz.studentsHint")}</CardDescription></CardHeader>
            <CardContent>
              {(r.students ?? []).length === 0 ? <p className="text-sm text-muted-foreground">{t("quiz.noStudents")}</p> : (
                <Table>
                  <TableHeader><TableRow><TableHead>{t("members.name")}</TableHead><TableHead>{t("quiz.score")}</TableHead>{(r.students ?? []).some((s) => s.pre_test != null) && <TableHead>{t("quiz.pre")}</TableHead>}</TableRow></TableHeader>
                  <TableBody>{(r.students ?? []).map((s) => (
                    <TableRow key={s.student_id}><TableCell>{name(s.student_id)}</TableCell><TableCell className="tabular-nums">{s.score}/{s.total}</TableCell>
                      {(r.students ?? []).some((x) => x.pre_test != null) && <TableCell className="tabular-nums">{pct(s.pre_test)}</TableCell>}</TableRow>
                  ))}</TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
