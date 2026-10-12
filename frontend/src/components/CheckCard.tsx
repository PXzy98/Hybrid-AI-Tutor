import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";

import { api, type CheckItem, type CheckResponse } from "../api/endpoints";
import Band from "./Band";

type Props = {
  item: CheckItem;
  sessionId?: string;
  onAnswered?: (result: CheckResponse) => void;
};

/** A check question under a tutor answer. The item has no answer key: grading happens on the server. */
export default function CheckCard({ item, sessionId = "", onAnswered }: Props) {
  const [choice, setChoice] = useState<string | null>(null);
  const qc = useQueryClient();
  const id = useId();
  const answer = useMutation({
    mutationFn: (c: string) => api.check(item.id, c, sessionId),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["profile"] });
      onAnswered?.(result);
    },
  });
  const result = answer.data;
  const options = Object.entries(item.options).sort(([a], [b]) => a.localeCompare(b));

  return (
    <form
      className="mt-3 rounded-lg border border-teal-200 bg-teal-50/40 p-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (choice) answer.mutate(choice);
      }}
      aria-describedby={`${id}-hint`}
    >
      <fieldset disabled={!!result || answer.isPending}>
        <legend className="mb-2 text-sm font-semibold text-teal-900">Check your understanding</legend>
        <p id={`${id}-stem`} className="mb-3 text-slate-900">{item.stem}</p>
        <div role="radiogroup" aria-labelledby={`${id}-stem`} className="space-y-2">
          {options.map(([key, text]) => {
            const isKey = result?.correct_choice === key;
            const isWrongChoice = result && choice === key && !result.correct;
            return (
              <label
                key={key}
                className={`flex cursor-pointer items-start gap-2 rounded-md border px-3 py-2 text-sm ${
                  isKey ? "border-emerald-500 bg-emerald-50" : isWrongChoice ? "border-rose-400 bg-rose-50" : "border-slate-200 bg-white"
                }`}
              >
                <input
                  type="radio"
                  name={`${id}-choice`}
                  value={key}
                  checked={choice === key}
                  onChange={() => setChoice(key)}
                  className="mt-0.5 accent-teal-700"
                />
                <span>
                  <span className="font-medium">{key}.</span> {text}
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>
      <p id={`${id}-hint`} className="sr-only">Choose one answer, then check it.</p>

      {!result && (
        <button type="submit" className="btn-primary mt-3" disabled={!choice || answer.isPending}>
          {answer.isPending ? "Checking…" : "Check answer"}
        </button>
      )}
      {answer.isError && (
        <p role="alert" className="mt-2 text-sm text-rose-700">{(answer.error as Error).message}</p>
      )}
      {result && (
        <div role="status" className="mt-3 space-y-2 text-sm">
          <p className={`font-semibold ${result.correct ? "text-emerald-800" : "text-rose-800"}`}>
            {result.correct ? "Correct!" : `Not quite. The answer is ${result.correct_choice}.`}
          </p>
          {result.explanation && <p className="text-slate-800">{result.explanation}</p>}
          <div className="flex flex-wrap items-center gap-2">
            {result.kc_band && <Band band={result.kc_band} label="This topic part" />}
            {result.next_kc && (
              <span className="text-slate-700">Suggested next: <strong>{result.next_kc.name}</strong></span>
            )}
          </div>
        </div>
      )}
    </form>
  );
}
