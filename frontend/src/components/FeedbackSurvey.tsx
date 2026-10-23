import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api, type SurveySubmission } from "../api/endpoints";
import { useI18n } from "../i18n";

const QUESTIONS = ["helpfulness", "material_relevance", "clarity", "source_confidence"] as const;

type Ratings = Omit<SurveySubmission, "topic">;
type ScoreKey = keyof Ratings;
const INITIAL: Record<ScoreKey, number> = {
  helpfulness: 0,
  material_relevance: 0,
  clarity: 0,
  source_confidence: 0,
};

/** Voluntary in-memory form; no student identifier, prompt, answer or comment sent. */
export default function FeedbackSurvey({ topic }: { topic: string }) {
  const [open, setOpen] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [ratings, setRatings] = useState<Record<ScoreKey, number>>({ ...INITIAL });
  const submit = useMutation({ mutationFn: api.submitSurvey });
  const { t } = useI18n();
  if (dismissed || submit.isSuccess) {
    return (
      <p className="text-sm text-emerald-800" role="status">
        {submit.isSuccess ? t("survey.done") : t("survey.skipped")}
      </p>
    );
  }
  if (!open) {
    return (
      <button type="button" className="btn-secondary text-sm" onClick={() => setOpen(true)}>
        {t("survey.open")}
      </button>
    );
  }

  const complete = QUESTIONS.every((q) => ratings[q] >= 1);
  function save(e: FormEvent) {
    e.preventDefault();
    if (!complete || submit.isPending) return;
    submit.mutate({ topic, ...ratings } as SurveySubmission);
  }
  return (
    <form onSubmit={save} aria-label={t("survey.form")}
          className="space-y-4 rounded-lg border border-teal-200 bg-white p-4 shadow-sm">
      <div>
        <h2 className="font-semibold text-slate-900">{t("survey.title")}</h2>
        <p className="text-xs text-slate-600">
          {t("survey.intro")}
        </p>
      </div>
      {QUESTIONS.map((q, i) => (
        <fieldset key={q}>
          <legend className="text-sm font-medium text-slate-800">{i + 1}. {t(`survey.q.${q}`)}</legend>
          <div className="mt-1 flex flex-wrap gap-3">
            {[1, 2, 3, 4, 5].map((score) => (
              <label key={score} className="flex items-center gap-1.5 text-sm">
                <input type="radio" name={q} value={score}
                       checked={ratings[q] === score}
                       onChange={() => setRatings((r) => ({ ...r, [q]: score }))} />
                {score}
              </label>
            ))}
          </div>
        </fieldset>
      ))}
      {submit.isError && (
        <p role="alert" className="text-sm text-rose-700">
          {t("survey.error")}
        </p>
      )}
      <div className="flex gap-2">
        <button type="submit" className="btn-primary" disabled={!complete || submit.isPending}>
          {submit.isPending ? t("survey.submitting") : t("survey.submit")}
        </button>
        <button type="button" className="btn-secondary"
                onClick={() => setDismissed(true)} disabled={submit.isPending}>{t("survey.skip")}</button>
      </div>
    </form>
  );
}
