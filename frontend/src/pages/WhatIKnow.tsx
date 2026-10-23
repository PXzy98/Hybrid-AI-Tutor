import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/endpoints";
import Band from "../components/Band";
import { useI18n } from "../i18n";
import type { MessageKey } from "../i18n/en";


/** The student's own profile: bands per knowledge component, never probabilities (design §7.4),
 * and the open misconceptions with their reviewed corrections (Step 12). */
export default function WhatIKnow() {
  const qc = useQueryClient();
  const { t } = useI18n();
  const profile = useQuery({ queryKey: ["profile"], queryFn: api.profile });
  const [confirming, setConfirming] = useState(false);
  const reset = useMutation({
    mutationFn: api.resetProfile,
    onSuccess: () => {
      setConfirming(false);
      qc.invalidateQueries({ queryKey: ["profile"] });
    },
  });

  if (profile.isLoading) return <p className="text-slate-600">{t("app.loading")}</p>;
  if (profile.isError || !profile.data) return <p role="alert" className="text-rose-700">{t("me.loadError")}</p>;
  const p = profile.data;

  if (!p.personalized) {
    return (
      <div className="card mx-auto max-w-xl space-y-3">
        <h1 className="text-xl font-semibold">{t("me.title")}</h1>
        <p className="text-sm text-slate-700">{t("me.noProfile")}</p>
        <Link to="/start" className="btn-primary">{t("me.personalize")}</Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">{t("me.title")}</h1>
          {p.preferences && (
            <p className="text-sm text-slate-600">
              {t("me.explanations", {
                sequencing: t(`me.pref.${p.preferences.sequencing ?? "example_first"}` as MessageKey),
                detail: t(`me.pref.${p.preferences.detail ?? "concise"}` as MessageKey),
              })}
            </p>
          )}
        </div>
        {!confirming ? (
          <button type="button" className="btn-secondary" onClick={() => setConfirming(true)}>{t("me.reset")}</button>
        ) : (
          <div role="alertdialog" aria-labelledby="reset-q" className="flex flex-wrap items-center gap-2 rounded-md border border-rose-200 bg-rose-50 px-3 py-2">
            <span id="reset-q" className="text-sm text-rose-900">{t("me.resetQuestion")}</span>
            <button type="button" className="btn bg-rose-700 py-1.5 text-white hover:bg-rose-800" onClick={() => reset.mutate()}
                    disabled={reset.isPending}>{t("me.resetYes")}</button>
            <button type="button" className="btn-secondary py-1.5" onClick={() => setConfirming(false)}>{t("me.cancel")}</button>
          </div>
        )}
      </div>

      {p.topics?.map((tp) => (
        <section key={tp.topic} className="card" aria-labelledby={`t-${tp.topic}`}>
          <h2 id={`t-${tp.topic}`} className="mb-3 font-semibold">{tp.name}</h2>
          <ul className="divide-y divide-slate-100">
            {tp.kcs.map((k) => (
              <li key={k.kc_id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <span>{k.name}</span>
                <Band band={k.band} />
              </li>
            ))}
          </ul>
          {tp.misconceptions && tp.misconceptions.length > 0 && (
            <div className="mt-4">
              <h3 className="mb-2 text-sm font-semibold">{t("me.working")}</h3>
              <ul className="space-y-2">
                {tp.misconceptions.map((m) => (
                  <li key={m.statement} className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm">
                    <p className="text-amber-900">
                      <span className="font-medium">{t("me.mixup")}</span> {m.statement}{" "}
                      <span className="text-xs text-amber-800">({t(`me.source.${m.status === "confirmed" ? "confirmed" : "suspected"}`)})</span>
                    </p>
                    <p className="mt-1 text-slate-800"><span className="font-medium">{t("me.true")}</span> {m.correction}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      ))}
    </div>
  );
}
