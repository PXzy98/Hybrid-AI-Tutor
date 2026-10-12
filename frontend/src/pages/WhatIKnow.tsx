import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/endpoints";
import Band from "../components/Band";

const PREF_LABELS: Record<string, string> = {
  example_first: "Example first",
  concept_first: "Idea first",
  concise: "Short answers",
  detailed: "Detailed answers",
};

/** The student's own profile: bands per knowledge component, never probabilities (design §7.4). */
export default function WhatIKnow() {
  const qc = useQueryClient();
  const profile = useQuery({ queryKey: ["profile"], queryFn: api.profile });
  const [confirming, setConfirming] = useState(false);
  const reset = useMutation({
    mutationFn: api.resetProfile,
    onSuccess: () => {
      setConfirming(false);
      qc.invalidateQueries({ queryKey: ["profile"] });
    },
  });

  if (profile.isLoading) return <p className="text-slate-600">Loading…</p>;
  if (profile.isError || !profile.data) return <p role="alert" className="text-rose-700">Could not load your profile.</p>;
  const p = profile.data;

  if (!p.personalized) {
    return (
      <div className="card mx-auto max-w-xl space-y-3">
        <h1 className="text-xl font-semibold">What I know</h1>
        <p className="text-sm text-slate-700">The tutor does not keep a learning profile for you, so there is nothing to show.</p>
        <Link to="/start" className="btn-primary">Personalize your tutor</Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">What I know</h1>
          {p.preferences && (
            <p className="text-sm text-slate-600">
              Explanations: {PREF_LABELS[p.preferences.sequencing ?? "example_first"]},{" "}
              {PREF_LABELS[p.preferences.detail ?? "concise"].toLowerCase()}.
            </p>
          )}
        </div>
        {!confirming ? (
          <button type="button" className="btn-secondary" onClick={() => setConfirming(true)}>Reset my learning data</button>
        ) : (
          <div role="alertdialog" aria-labelledby="reset-q" className="flex flex-wrap items-center gap-2 rounded-md border border-rose-200 bg-rose-50 px-3 py-2">
            <span id="reset-q" className="text-sm text-rose-900">Forget everything the tutor learned about you?</span>
            <button type="button" className="btn bg-rose-700 py-1.5 text-white hover:bg-rose-800" onClick={() => reset.mutate()}
                    disabled={reset.isPending}>Yes, reset</button>
            <button type="button" className="btn-secondary py-1.5" onClick={() => setConfirming(false)}>Cancel</button>
          </div>
        )}
      </div>

      {p.topics?.map((t) => (
        <section key={t.topic} className="card" aria-labelledby={`t-${t.topic}`}>
          <h2 id={`t-${t.topic}`} className="mb-3 font-semibold">{t.name}</h2>
          <ul className="divide-y divide-slate-100">
            {t.kcs.map((k) => (
              <li key={k.kc_id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <span>{k.name}</span>
                <Band band={k.band} />
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
