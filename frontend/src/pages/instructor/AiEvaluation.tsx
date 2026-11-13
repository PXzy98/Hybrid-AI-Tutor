import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { api, type Course, type Evaluation, type EvaluationQuestion } from "@/api/endpoints";
import { ErrorNote } from "@/components/common";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useI18n } from "@/i18n";
import type { MessageKey } from "@/i18n/en";

const TYPES = ["concept", "application", "logistics"] as const;
type Group = { questions?: number; local_score?: number | null; cloud_score?: number | null };
type Result = { question_id: number; module: string; type: string; local: { score: number | null }; cloud: { score: number | null };
  judge_reason?: string; spot_check?: { agrees_with_judge: boolean } | null };

/** Tier 4: local against cloud answers on questions written from the course material. Course material goes to the
 * cloud model only after the explicit confirmation. */
export default function AiEvaluation({ course }: { course: Course }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [selected, setSelected] = useState<number | null>(null);
  const [perModule, setPerModule] = useState(5);
  const list = useQuery({ queryKey: ["ai-evals", course.id], queryFn: () => api.evaluations(course.id) });
  const start = useMutation({
    mutationFn: () => api.createEvaluation(course.id, { questions_per_module: perModule }),
    onSuccess: (e) => { setSelected(e.id); qc.invalidateQueries({ queryKey: ["ai-evals", course.id] }); },
  });
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>{t("eval.title")}</CardTitle><CardDescription>{t("eval.hint")}</CardDescription></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-end gap-3">
            <div className="grid gap-1.5"><Label htmlFor="eval-count">{t("eval.perModule")}</Label>
              <Input id="eval-count" type="number" min={1} max={20} className="w-24" value={perModule} onChange={(e) => setPerModule(Number(e.target.value))} /></div>
            <Button type="button" onClick={() => start.mutate()} disabled={start.isPending}>{t("eval.start")}</Button>
          </div>
          <ErrorNote error={start.error ?? list.error} />
          <ul className="divide-y text-sm">
            {list.data?.map((e) => (
              <li key={e.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span>#{e.id} <Badge variant="secondary">{t(`eval.status.${e.status}` as MessageKey)}</Badge> {t("quiz.questionsN", { n: e.questions })}</span>
                <Button type="button" size="sm" variant="outline" aria-label={t("eval.openFor", { id: e.id })} onClick={() => setSelected(e.id)}>{t("ai.open")}</Button>
              </li>
            ))}
            {list.data?.length === 0 && <li className="py-2 text-muted-foreground">{t("eval.none")}</li>}
          </ul>
        </CardContent>
      </Card>
      {selected !== null && <EvaluationDetail key={selected} course={course} id={selected} />}
    </div>
  );
}

function EvaluationDetail({ course, id }: { course: Course; id: number }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const evaluation = useQuery({
    queryKey: ["ai-eval", course.id, id],
    queryFn: () => api.evaluation(course.id, id),
    refetchInterval: (q) => (q.state.data?.status === "generating" || q.state.data?.status === "running" ? 2000 : false),
  });
  const e = evaluation.data;
  if (evaluation.error) return <ErrorNote error={evaluation.error} />;
  if (!e) return <p className="text-muted-foreground">{t("app.loading")}</p>;
  const update = (fresh: Evaluation) => {
    qc.setQueryData(["ai-eval", course.id, id], fresh);
    qc.invalidateQueries({ queryKey: ["ai-evals", course.id] });
  };
  return (
    <Card aria-label={t("eval.detail", { id })}>
      <CardHeader><CardTitle className="flex items-center gap-2">#{e.id} <Badge variant="secondary">{t(`eval.status.${e.status}` as MessageKey)}</Badge></CardTitle></CardHeader>
      <CardContent className="space-y-4">
        {(e.status === "generating" || e.status === "running") && (
          <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 aria-hidden className="size-4 animate-spin" />{t(e.status === "generating" ? "eval.generating" : "eval.running")}</p>
        )}
        {e.status === "failed" && <Alert variant="destructive" role="alert">{t("eval.failed")}{e.error ? ` ${e.error}` : ""}</Alert>}
        {e.status === "review" && <ReviewForm course={course} evaluation={e} onChange={update} />}
        {e.status === "done" && <Report course={course} evaluation={e} onChange={update} />}
      </CardContent>
    </Card>
  );
}

function ReviewForm({ course, evaluation, onChange }: { course: Course; evaluation: Evaluation; onChange: (e: Evaluation) => void }) {
  const { t } = useI18n();
  const modules = useQuery({ queryKey: ["modules", course.id], queryFn: () => api.modules(course.id) });
  const [questions, setQuestions] = useState<EvaluationQuestion[]>(
    evaluation.questions.map((q) => ({ module_id: Number(q.module_id), type: q.type as EvaluationQuestion["type"], question: String(q.question), reference: String(q.reference ?? "") })));
  const [confirmOpen, setConfirmOpen] = useState(false);
  const save = useMutation({ mutationFn: () => api.setEvaluationQuestions(course.id, evaluation.id, questions), onSuccess: onChange });
  const run = useMutation({
    mutationFn: async () => {
      await api.setEvaluationQuestions(course.id, evaluation.id, questions);
      return api.runEvaluation(course.id, evaluation.id, true);
    },
    onSuccess: (e) => { setConfirmOpen(false); onChange(e); },
  });
  const set = (i: number, patch: Partial<EvaluationQuestion>) => setQuestions(questions.map((q, j) => (j === i ? { ...q, ...patch } : q)));
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">{t("eval.reviewHint")}</p>
      {questions.map((q, i) => (
        <div key={i} className="space-y-2 rounded-lg border p-3" role="group" aria-label={t("quiz.questionN", { n: i + 1 })}>
          <div className="grid gap-2 sm:grid-cols-2">
            <Select aria-label={t("content.module")} value={q.module_id} onChange={(e) => set(i, { module_id: Number(e.target.value) })}>
              {modules.data?.map((m) => <option key={m.id} value={m.id}>{m.title}</option>)}
            </Select>
            <Select aria-label={t("quiz.questionKind")} value={q.type} onChange={(e) => set(i, { type: e.target.value as EvaluationQuestion["type"] })}>
              {TYPES.map((x) => <option key={x} value={x}>{t(`eval.type.${x}` as MessageKey)}</option>)}
            </Select>
          </div>
          <Textarea aria-label={t("quiz.question")} value={q.question} onChange={(e) => set(i, { question: e.target.value })} />
          <Textarea aria-label={t("eval.reference")} value={q.reference ?? ""} onChange={(e) => set(i, { reference: e.target.value })} />
          <Button type="button" size="sm" variant="ghost" aria-label={t("quiz.removeQuestion", { n: i + 1 })} onClick={() => setQuestions(questions.filter((_, j) => j !== i))}><Trash2 aria-hidden />{t("members.remove")}</Button>
        </div>
      ))}
      <Button type="button" variant="outline" disabled={!modules.data?.length}
              onClick={() => setQuestions([...questions, { module_id: modules.data?.[0]?.id ?? 0, type: "concept", question: "", reference: "" }])}><Plus aria-hidden />{t("quiz.addQuestion")}</Button>
      <ErrorNote error={save.error} />
      <div className="flex flex-wrap gap-3">
        <Button type="button" variant="outline" onClick={() => save.mutate()} disabled={save.isPending}>{t("eval.saveQuestions")}</Button>
        <Button type="button" onClick={() => setConfirmOpen(true)} disabled={questions.length === 0}>{t("eval.run")}</Button>
      </div>
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("eval.confirmTitle")}</DialogTitle>
            <DialogDescription>{t("eval.confirmBody")}</DialogDescription>
          </DialogHeader>
          <ErrorNote error={run.error} />
          <DialogFooter>
            <DialogClose asChild><Button type="button" variant="outline">{t("end.cancel")}</Button></DialogClose>
            <Button type="button" variant="destructive" onClick={() => run.mutate()} disabled={run.isPending}>{t("eval.confirm")}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Report({ course, evaluation, onChange }: { course: Course; evaluation: Evaluation; onChange: (e: Evaluation) => void }) {
  const { t } = useI18n();
  const report = evaluation.report as { overall?: Group; by_module?: Record<string, Group>; by_type?: Record<string, Group>; spot_checks?: number; spot_checks_agreeing?: number };
  const results = evaluation.results as unknown as Result[];
  const check = useMutation({
    mutationFn: (v: { q: number; agrees: boolean }) => api.spotCheck(course.id, evaluation.id, v.q, v.agrees),
    onSuccess: onChange,
  });
  const score = (x: number | null | undefined) => (x == null ? "—" : x.toFixed(2));
  const rows: [string, Group][] = [
    [t("eval.overall"), report.overall ?? {}],
    ...Object.entries(report.by_module ?? {}),
    ...Object.entries(report.by_type ?? {}).map(([k, v]) => [t(`eval.type.${k}` as MessageKey), v] as [string, Group]),
  ];
  return (
    <div className="space-y-4">
      <Table aria-label={t("eval.report")}>
        <TableHeader><TableRow><TableHead>{t("eval.group")}</TableHead><TableHead>{t("quiz.question")}</TableHead><TableHead>{t("eval.local")}</TableHead><TableHead>{t("eval.cloud")}</TableHead></TableRow></TableHeader>
        <TableBody>{rows.map(([name, g]) => (
          <TableRow key={name}><TableCell className="font-medium">{name}</TableCell><TableCell className="tabular-nums">{g.questions ?? 0}</TableCell>
            <TableCell className="tabular-nums">{score(g.local_score)}</TableCell><TableCell className="tabular-nums">{score(g.cloud_score)}</TableCell></TableRow>
        ))}</TableBody>
      </Table>
      <p className="text-sm text-muted-foreground">{t("eval.spotSummary", { n: report.spot_checks ?? 0, a: report.spot_checks_agreeing ?? 0 })}</p>
      <ErrorNote error={check.error} />
      <ul className="space-y-2 text-sm">
        {results.map((r) => (
          <li key={r.question_id} className="rounded-md border p-3">
            <p className="font-medium">#{r.question_id} · {r.module} · {t(`eval.type.${r.type}` as MessageKey)}</p>
            <p className="text-muted-foreground">{t("eval.local")} {r.local.score ?? "—"} · {t("eval.cloud")} {r.cloud.score ?? "—"}{r.judge_reason ? ` · ${r.judge_reason}` : ""}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Button type="button" size="sm" variant={r.spot_check?.agrees_with_judge === true ? "default" : "outline"} onClick={() => check.mutate({ q: r.question_id, agrees: true })}>{t("eval.agree")}</Button>
              <Button type="button" size="sm" variant={r.spot_check?.agrees_with_judge === false ? "default" : "outline"} onClick={() => check.mutate({ q: r.question_id, agrees: false })}>{t("eval.disagree")}</Button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
