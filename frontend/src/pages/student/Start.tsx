import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { api, type Course, type OnboardingResult } from "@/api/endpoints";
import Band from "@/components/Band";
import { choiceRow, EmptyState, ErrorNote, Loading, PageHeader } from "@/components/common";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useI18n } from "@/i18n";

type Prefs = { sequencing?: "example_first" | "concept_first"; detail?: "concise" | "detailed" };

/** Cold start: consent, two preference questions and a short diagnostic for one module. Every part can be
 * skipped. Nothing is stored without consent. */
export default function Start({ course }: { course: Course }) {
  const { t } = useI18n();
  const modules = useQuery({ queryKey: ["modules", course.id], queryFn: () => api.modules(course.id) });
  const [chosen, setChosen] = useState<number | null>(null);
  const moduleId = chosen ?? modules.data?.[0]?.id ?? null;
  if (modules.isLoading) return <Loading variant="form" />;
  if (moduleId === null) return <EmptyState icon={BookOpen} title={t("empty.modules.title")}>{t("nav.noModules")}</EmptyState>;
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader title={t("onb.title")} description={t("onb.intro")} actions={
        <div className="grid gap-1.5">
          <Label htmlFor="onb-module">{t("onb.module")}</Label>
          <Select id="onb-module" value={moduleId} onChange={(e) => setChosen(Number(e.target.value))}>
            {modules.data?.map((m) => <option key={m.id} value={m.id}>{m.title}</option>)}
          </Select>
        </div>
      } />
      <OnboardingForm key={moduleId} course={course} moduleId={moduleId} />
    </div>
  );
}

function OnboardingForm({ course, moduleId }: { course: Course; moduleId: number }) {
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const info = useQuery({ queryKey: ["onboarding", course.id, moduleId, lang], queryFn: () => api.onboarding(course.id, moduleId, lang) });
  const [consent, setConsent] = useState<boolean | null>(null);
  const [prefs, setPrefs] = useState<Prefs>({});
  const [skipPrefs, setSkipPrefs] = useState(false);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [skipDiagnostic, setSkipDiagnostic] = useState(false);
  const submit = useMutation({
    mutationFn: () => api.submitOnboarding(course.id, {
      module_id: moduleId,
      consent: consent ?? info.data?.consent_given ?? null,
      preferences: skipPrefs ? {} : prefs,
      answers: skipDiagnostic ? [] : Object.entries(answers).map(([item_id, choice]) => ({ item_id, choice: choice as "A" })),
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["profile", course.id] }),
  });

  if (submit.data) return <Done result={submit.data} courseId={course.id} />;
  if (info.isLoading) return <Loading variant="form" />;
  if (info.isError || !info.data) return <ErrorNote error={info.error ?? new Error(t("onb.loadError"))} />;
  const data = info.data;
  const agreed = consent ?? data.consent_given ?? false;

  return (
    <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); submit.mutate(); }}>
      <Step id="consent-title" title={t("onb.consentTitle")}>
        <div className="space-y-2 text-sm leading-relaxed">
          {sentences(data.consent_text).map((sentence) => <p key={sentence}>{sentence}</p>)}
        </div>
        <label className={choiceRow(agreed)}>
          <input type="checkbox" className="mt-0.5 accent-primary" checked={agreed} onChange={(e) => setConsent(e.target.checked)} />
          <span>{t("onb.consentAgree")}</span>
        </label>
      </Step>

      <Step id="prefs-title" title={t("onb.prefsTitle")} action={
        <Button type="button" variant="ghost" size="sm" onClick={() => setSkipPrefs(!skipPrefs)} aria-pressed={skipPrefs}>
          {skipPrefs ? t("onb.answer") : t("onb.skip")}
        </Button>
      }>
        {!skipPrefs && data.preference_questions.map((q) => (
          <fieldset key={q.id}>
            <legend className="mb-2 text-sm font-medium">{q.question}</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              {q.options.map((o) => (
                <label key={o.value} className={choiceRow(prefs[q.id] === o.value)}>
                  <input type="radio" name={q.id} value={o.value} className="mt-0.5 accent-primary" checked={prefs[q.id] === o.value}
                         onChange={() => setPrefs({ ...prefs, [q.id]: o.value } as Prefs)} />
                  <span>{o.label}</span>
                </label>
              ))}
            </div>
          </fieldset>
        ))}
      </Step>

      {/* a module without check items has nothing to ask: no empty step */}
      {data.diagnostic.length > 0 && <Step id="diag-title" title={t("onb.diagTitle")} action={
        <Button type="button" variant="ghost" size="sm" onClick={() => setSkipDiagnostic(!skipDiagnostic)} aria-pressed={skipDiagnostic}>
          {skipDiagnostic ? t("onb.answer") : t("onb.skip")}
        </Button>
      }>
        {!skipDiagnostic && data.diagnostic.map((item, n) => (
          <div key={item.id} className="border-t pt-4 first:border-0 first:pt-0">
            <fieldset>
              <legend className="mb-2 text-sm"><span className="font-medium">{n + 1}.</span> {item.stem}</legend>
              <div className="space-y-2">
                {Object.entries(item.options).sort(([a], [b]) => a.localeCompare(b)).map(([key, text]) => (
                  <label key={key} className={choiceRow(answers[item.id] === key)}>
                    <input type="radio" name={item.id} value={key} className="mt-0.5 accent-primary" checked={answers[item.id] === key}
                           onChange={() => setAnswers({ ...answers, [item.id]: key })} />
                    <span><span className="font-medium">{key}.</span> {text}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          </div>
        ))}
        {!agreed && !skipDiagnostic && <Alert variant="warning" icon>{t("onb.noConsent")}</Alert>}
      </Step>}

      <ErrorNote error={submit.error} />
      {/* floats a little above the bottom edge, so it never sits against the footer line */}
      <div className="sticky bottom-2 z-10 flex flex-wrap gap-3 rounded-xl border bg-background p-3 shadow-sm">
        <Button loading={submit.isPending} type="submit" disabled={submit.isPending}>{submit.isPending ? t("onb.saving") : t("onb.save")}</Button>
        <Button asChild variant="outline"><Link to={`/courses/${course.id}/chat`}>{t("onb.skipAll")}</Link></Button>
      </div>
    </form>
  );
}

/** The sentences of a text, one per paragraph: a long consent text is easier to read in short pieces. */
export const sentences = (text: string) => text.split(/(?<=[.!?])\s+(?=[A-ZÀ-ÝÉ])/).map((x) => x.trim()).filter(Boolean);

/** One part of the form, numbered down the left edge. The number comes from the title ("1. ..."), so the text
 *  read aloud stays the same. */
function Step({ id, title, action, children }: { id: string; title: string; action?: ReactNode; children: ReactNode }) {
  const m = /^(\d+)\.\s*(.*)$/.exec(title);
  return (
    <section aria-labelledby={id} className="grid grid-cols-[1.75rem_minmax(0,1fr)] gap-x-3 sm:gap-x-4">
      <span aria-hidden className="mt-4 flex size-7 items-center justify-center rounded-full border bg-background text-xs font-semibold tabular-nums text-muted-foreground">
        {m?.[1]}
      </span>
      <div className="space-y-4 rounded-xl border bg-card p-4 sm:p-5">
        <div className="flex items-center justify-between gap-3">
          <h3 id={id} className="text-sm font-semibold">{m ? <><span className="sr-only">{m[1]}. </span>{m[2]}</> : title}</h3>
          {action}
        </div>
        {children}
      </div>
    </section>
  );
}

function Done({ result, courseId }: { result: OnboardingResult; courseId: number }) {
  const { t } = useI18n();
  return (
    <Card role="status" className="mx-auto max-w-3xl">
      <CardHeader><CardTitle>{result.personalized ? t("onb.ready") : t("onb.saved")}</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        {result.personalized ? (
          <>
            <p className="text-sm">{t("onb.startsAt")}</p>
            <ul className="space-y-1.5">
              {result.kcs?.map((k) => (
                <li key={k.kc_id} className="flex items-center justify-between gap-3 text-sm"><span>{k.name}</span><Band band={k.band} /></li>
              ))}
            </ul>
          </>
        ) : <p className="text-sm">{t("onb.noProfile")}</p>}
        <Button asChild><Link to={`/courses/${courseId}/chat`}>{t("onb.startChat")}</Link></Button>
      </CardContent>
    </Card>
  );
}
