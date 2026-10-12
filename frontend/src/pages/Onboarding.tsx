import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { api, type OnboardingResult } from "../api/endpoints";
import Band from "../components/Band";
import TopicPicker from "../components/TopicPicker";

type Prefs = { sequencing?: "example_first" | "concept_first"; detail?: "concise" | "detailed" };

/** Cold start (design §5.5): consent, two preference questions and a short diagnostic. Every part can be
 * skipped. Nothing is stored without consent. */
export default function Onboarding() {
  const [topic, setTopic] = useState("high_blood_pressure");
  const info = useQuery({ queryKey: ["onboarding", topic], queryFn: () => api.onboardingInfo(topic) });
  const qc = useQueryClient();
  const [consent, setConsent] = useState<boolean | null>(null);
  const [prefs, setPrefs] = useState<Prefs>({});
  const [skipPrefs, setSkipPrefs] = useState(false);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [skipDiagnostic, setSkipDiagnostic] = useState(false);
  const submit = useMutation({
    mutationFn: () =>
      api.submitOnboarding({
        topic,
        consent: consent ?? info.data?.consent_given ?? null,
        preferences: skipPrefs ? {} : prefs,
        answers: skipDiagnostic ? [] : Object.entries(answers).map(([item_id, choice]) => ({ item_id, choice: choice as "A" })),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["profile"] }),
  });

  if (submit.data) return <Done result={submit.data} />;
  if (info.isLoading) return <p className="text-slate-600">Loading…</p>;
  if (info.isError || !info.data) return <p role="alert" className="text-rose-700">Could not load onboarding.</p>;
  const data = info.data;
  const agreed = consent ?? data.consent_given ?? false;

  return (
    <form
      className="mx-auto max-w-3xl space-y-6"
      onSubmit={(e) => {
        e.preventDefault();
        submit.mutate();
      }}
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Personalize your tutor</h1>
          <p className="text-sm text-slate-600">Each part is optional. You can change everything later.</p>
        </div>
        <TopicPicker value={topic} onChange={(t) => { setTopic(t); setAnswers({}); }} />
      </div>

      <section className="card space-y-3" aria-labelledby="consent-title">
        <h2 id="consent-title" className="font-semibold">1. Your learning profile</h2>
        <p className="text-sm leading-relaxed text-slate-700">{data.consent_text}</p>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-1 accent-teal-700" checked={agreed}
                 onChange={(e) => setConsent(e.target.checked)} />
          <span>I agree that the tutor keeps a learning profile for me as described above.</span>
        </label>
      </section>

      <section className="card space-y-4" aria-labelledby="prefs-title">
        <div className="flex items-center justify-between">
          <h2 id="prefs-title" className="font-semibold">2. How you like to learn</h2>
          <button type="button" className="btn-link" onClick={() => setSkipPrefs(!skipPrefs)} aria-pressed={skipPrefs}>
            {skipPrefs ? "Answer these" : "Skip"}
          </button>
        </div>
        {!skipPrefs && data.preference_questions.map((q) => (
          <fieldset key={q.id}>
            <legend className="mb-2 text-sm font-medium text-slate-800">{q.question}</legend>
            <div className="flex flex-wrap gap-2">
              {q.options.map((o) => (
                <label key={o.value} className="flex cursor-pointer items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm">
                  <input type="radio" name={q.id} value={o.value} className="accent-teal-700"
                         checked={prefs[q.id] === o.value}
                         onChange={() => setPrefs({ ...prefs, [q.id]: o.value } as Prefs)} />
                  {o.label}
                </label>
              ))}
            </div>
          </fieldset>
        ))}
      </section>

      <section className="card space-y-4" aria-labelledby="diag-title">
        <div className="flex items-center justify-between">
          <h2 id="diag-title" className="font-semibold">3. Quick check of what you already know</h2>
          <button type="button" className="btn-link" onClick={() => setSkipDiagnostic(!skipDiagnostic)}
                  aria-pressed={skipDiagnostic}>
            {skipDiagnostic ? "Answer these" : "Skip"}
          </button>
        </div>
        {data.diagnostic.length === 0 && (
          <p className="text-sm text-slate-600">No questions are available for this topic yet.</p>
        )}
        {!skipDiagnostic && data.diagnostic.map((item, n) => (
          <fieldset key={item.id} className="border-t border-slate-100 pt-3 first:border-0 first:pt-0">
            <legend className="mb-2 text-sm text-slate-900"><span className="font-medium">{n + 1}.</span> {item.stem}</legend>
            <div className="space-y-1.5">
              {Object.entries(item.options).sort(([a], [b]) => a.localeCompare(b)).map(([key, text]) => (
                <label key={key} className="flex cursor-pointer items-start gap-2 text-sm">
                  <input type="radio" name={item.id} value={key} className="mt-0.5 accent-teal-700"
                         checked={answers[item.id] === key}
                         onChange={() => setAnswers({ ...answers, [item.id]: key })} />
                  <span><span className="font-medium">{key}.</span> {text}</span>
                </label>
              ))}
            </div>
          </fieldset>
        ))}
        {!agreed && data.diagnostic.length > 0 && !skipDiagnostic && (
          <p className="text-sm text-amber-800">Without consent your answers are not saved.</p>
        )}
      </section>

      {submit.isError && <p role="alert" className="text-sm text-rose-700">{(submit.error as Error).message}</p>}
      <div className="flex gap-3">
        <button type="submit" className="btn-primary" disabled={submit.isPending}>
          {submit.isPending ? "Saving…" : "Save and start"}
        </button>
        <Link to="/chat" className="btn-secondary">Skip all</Link>
      </div>
    </form>
  );
}

function Done({ result }: { result: OnboardingResult }) {
  return (
    <div className="card mx-auto max-w-2xl space-y-4" role="status">
      <h1 className="text-xl font-semibold">{result.personalized ? "You're all set" : "Saved"}</h1>
      {result.personalized ? (
        <>
          <p className="text-sm text-slate-700">Here is where the tutor will start for each part of the topic:</p>
          <ul className="space-y-1.5">
            {result.kcs?.map((k) => (
              <li key={k.kc_id} className="flex items-center justify-between gap-3 text-sm">
                <span>{k.name}</span>
                <Band band={k.band} />
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="text-sm text-slate-700">The tutor will answer your questions without a learning profile.</p>
      )}
      <Link to="/chat" className="btn-primary">Start chatting</Link>
    </div>
  );
}
