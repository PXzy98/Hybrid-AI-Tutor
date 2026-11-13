import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { api, type Course, type OnboardingResult } from "@/api/endpoints";
import Band from "@/components/Band";
import { ErrorNote } from "@/components/common";
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
  if (modules.isLoading) return <p className="text-muted-foreground">{t("app.loading")}</p>;
  if (moduleId === null) return <p className="text-muted-foreground">{t("nav.noModules")}</p>;
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">{t("onb.title")}</h2>
          <p className="text-sm text-muted-foreground">{t("onb.intro")}</p>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="onb-module">{t("onb.module")}</Label>
          <Select id="onb-module" value={moduleId} onChange={(e) => setChosen(Number(e.target.value))}>
            {modules.data?.map((m) => <option key={m.id} value={m.id}>{m.title}</option>)}
          </Select>
        </div>
      </div>
      <OnboardingForm key={moduleId} course={course} moduleId={moduleId} />
    </div>
  );
}

function OnboardingForm({ course, moduleId }: { course: Course; moduleId: number }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const info = useQuery({ queryKey: ["onboarding", course.id, moduleId], queryFn: () => api.onboarding(course.id, moduleId) });
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
  if (info.isLoading) return <p className="text-muted-foreground">{t("app.loading")}</p>;
  if (info.isError || !info.data) return <ErrorNote error={info.error ?? new Error(t("onb.loadError"))} />;
  const data = info.data;
  const agreed = consent ?? data.consent_given ?? false;

  return (
    <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); submit.mutate(); }}>
      <Card aria-labelledby="consent-title">
        <CardHeader><CardTitle><h3 id="consent-title">{t("onb.consentTitle")}</h3></CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm leading-relaxed">{data.consent_text}</p>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-1 accent-primary" checked={agreed} onChange={(e) => setConsent(e.target.checked)} />
            <span>{t("onb.consentAgree")}</span>
          </label>
        </CardContent>
      </Card>

      <Card aria-labelledby="prefs-title">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle><h3 id="prefs-title">{t("onb.prefsTitle")}</h3></CardTitle>
            <Button type="button" variant="link" size="sm" onClick={() => setSkipPrefs(!skipPrefs)} aria-pressed={skipPrefs}>
              {skipPrefs ? t("onb.answer") : t("onb.skip")}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {!skipPrefs && data.preference_questions.map((q) => (
            <fieldset key={q.id}>
              <legend className="mb-2 text-sm font-medium">{q.question}</legend>
              <div className="flex flex-wrap gap-2">
                {q.options.map((o) => (
                  <label key={o.value} className="flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm">
                    <input type="radio" name={q.id} value={o.value} className="accent-primary" checked={prefs[q.id] === o.value}
                           onChange={() => setPrefs({ ...prefs, [q.id]: o.value } as Prefs)} />
                    {o.label}
                  </label>
                ))}
              </div>
            </fieldset>
          ))}
        </CardContent>
      </Card>

      <Card aria-labelledby="diag-title">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle><h3 id="diag-title">{t("onb.diagTitle")}</h3></CardTitle>
            <Button type="button" variant="link" size="sm" onClick={() => setSkipDiagnostic(!skipDiagnostic)} aria-pressed={skipDiagnostic}>
              {skipDiagnostic ? t("onb.answer") : t("onb.skip")}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {data.diagnostic.length === 0 && <p className="text-sm text-muted-foreground">{t("onb.noItems")}</p>}
          {!skipDiagnostic && data.diagnostic.map((item, n) => (
            <fieldset key={item.id} className="border-t pt-3 first:border-0 first:pt-0">
              <legend className="mb-2 text-sm"><span className="font-medium">{n + 1}.</span> {item.stem}</legend>
              <div className="space-y-1.5">
                {Object.entries(item.options).sort(([a], [b]) => a.localeCompare(b)).map(([key, text]) => (
                  <label key={key} className="flex cursor-pointer items-start gap-2 text-sm">
                    <input type="radio" name={item.id} value={key} className="mt-0.5 accent-primary" checked={answers[item.id] === key}
                           onChange={() => setAnswers({ ...answers, [item.id]: key })} />
                    <span><span className="font-medium">{key}.</span> {text}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          ))}
          {!agreed && data.diagnostic.length > 0 && !skipDiagnostic && <Alert variant="warning">{t("onb.noConsent")}</Alert>}
        </CardContent>
      </Card>

      <ErrorNote error={submit.error} />
      <div className="flex gap-3">
        <Button type="submit" disabled={submit.isPending}>{submit.isPending ? t("onb.saving") : t("onb.save")}</Button>
        <Button asChild variant="outline"><Link to={`/courses/${course.id}/chat`}>{t("onb.skipAll")}</Link></Button>
      </div>
    </form>
  );
}

function Done({ result, courseId }: { result: OnboardingResult; courseId: number }) {
  const { t } = useI18n();
  return (
    <Card role="status">
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
