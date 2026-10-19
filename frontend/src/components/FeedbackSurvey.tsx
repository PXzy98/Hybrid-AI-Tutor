import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api, type SurveySubmission } from "../api/endpoints";

const QUESTIONS = [
  { key: "helpfulness", label: "How helpful was the tutor's explanation?" },
  { key: "material_relevance", label: "How relevant were the retrieved course materials?" },
  { key: "clarity", label: "How easy was the explanation to understand?" },
  { key: "source_confidence", label: "How confident are you that the answer was supported by its sources?" },
] as const;

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
  if (dismissed || submit.isSuccess) {
    return (
      <p className="text-sm text-emerald-800" role="status">
        {submit.isSuccess ? "Thank you. Your anonymous ratings were saved." : "Feedback skipped."}
      </p>
    );
  }
  if (!open) {
    return (
      <button type="button" className="btn-secondary text-sm" onClick={() => setOpen(true)}>
        Rate this answer (optional)
      </button>
    );
  }

  const complete = QUESTIONS.every((q) => ratings[q.key] >= 1);
  function save(e: FormEvent) {
    e.preventDefault();
    if (!complete || submit.isPending) return;
    submit.mutate({ topic, ...ratings } as SurveySubmission);
  }
  return (
    <form onSubmit={save} aria-label="Student feedback survey"
          className="space-y-4 rounded-lg border border-teal-200 bg-white p-4 shadow-sm">
      <div>
        <h2 className="font-semibold text-slate-900">Student feedback (optional)</h2>
        <p className="text-xs text-slate-600">
          Four ratings, 1 = very poor and 5 = excellent. We store only the topic and ratings.
          Please do not enter personal or medical information. You can skip.
        </p>
      </div>
      {QUESTIONS.map((q, i) => (
        <fieldset key={q.key}>
          <legend className="text-sm font-medium text-slate-800">{i + 1}. {q.label}</legend>
          <div className="mt-1 flex flex-wrap gap-3">
            {[1, 2, 3, 4, 5].map((score) => (
              <label key={score} className="flex items-center gap-1.5 text-sm">
                <input type="radio" name={q.key} value={score}
                       checked={ratings[q.key] === score}
                       onChange={() => setRatings((r) => ({ ...r, [q.key]: score }))} />
                {score}
              </label>
            ))}
          </div>
        </fieldset>
      ))}
      {submit.isError && (
        <p role="alert" className="text-sm text-rose-700">
          Could not save feedback. Please try again.
        </p>
      )}
      <div className="flex gap-2">
        <button type="submit" className="btn-primary" disabled={!complete || submit.isPending}>
          {submit.isPending ? "Submitting..." : "Submit feedback"}
        </button>
        <button type="button" className="btn-secondary"
                onClick={() => setDismissed(true)} disabled={submit.isPending}>Skip</button>
      </div>
    </form>
  );
}
