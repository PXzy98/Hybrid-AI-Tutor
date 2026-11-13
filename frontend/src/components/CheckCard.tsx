import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";

import { api, type CheckItem, type CheckResponse } from "@/api/endpoints";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n";
import Band from "./Band";
import { ErrorNote } from "./common";

type Props = {
  courseId: number;
  item: CheckItem;
  onAnswered?: (result: CheckResponse) => void;
};

/** A check question under a tutor answer. The item has no answer key: grading happens on the server. */
export default function CheckCard({ courseId, item, onAnswered }: Props) {
  const [choice, setChoice] = useState<string | null>(null);
  const qc = useQueryClient();
  const id = useId();
  const { t } = useI18n();
  const answer = useMutation({
    mutationFn: (c: string) => api.check(courseId, item.id, c),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["profile", courseId] });
      onAnswered?.(result);
    },
  });
  const result = answer.data;
  const options = Object.entries(item.options).sort(([a], [b]) => a.localeCompare(b));

  return (
    <form
      className="mt-3 rounded-lg border bg-muted/40 p-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (choice) answer.mutate(choice);
      }}
      aria-describedby={`${id}-hint`}
    >
      <fieldset disabled={!!result || answer.isPending}>
        <legend className="mb-2 text-sm font-semibold text-primary">{t("check.legend")}</legend>
        <p id={`${id}-stem`} className="mb-3">{item.stem}</p>
        <div role="radiogroup" aria-labelledby={`${id}-stem`} className="space-y-2">
          {options.map(([key, text]) => {
            const isKey = result?.correct_choice === key;
            const isWrongChoice = result && choice === key && !result.correct;
            return (
              <label
                key={key}
                className={`flex cursor-pointer items-start gap-2 rounded-md border px-3 py-2 text-sm ${
                  isKey ? "border-emerald-500 bg-emerald-50 dark:bg-emerald-950" : isWrongChoice ? "border-rose-400 bg-rose-50 dark:bg-rose-950" : "bg-card"
                }`}
              >
                <input type="radio" name={`${id}-choice`} value={key} checked={choice === key}
                       onChange={() => setChoice(key)} className="mt-0.5 accent-primary" />
                <span><span className="font-medium">{key}.</span> {text}</span>
              </label>
            );
          })}
        </div>
      </fieldset>
      <p id={`${id}-hint`} className="sr-only">{t("check.hint")}</p>

      {!result && (
        <Button type="submit" className="mt-3" disabled={!choice || answer.isPending}>
          {answer.isPending ? t("check.busy") : t("check.submit")}
        </Button>
      )}
      {answer.isError && <div className="mt-2"><ErrorNote error={answer.error} /></div>}
      {result && (
        <div role="status" className="mt-3 space-y-2 text-sm">
          <p className={`font-semibold ${result.correct ? "text-emerald-700 dark:text-emerald-300" : "text-rose-700 dark:text-rose-300"}`}>
            {result.correct ? t("check.correct") : t("check.wrong", { choice: result.correct_choice })}
          </p>
          {result.explanation && <p>{result.explanation}</p>}
          <div className="flex flex-wrap items-center gap-2">
            {result.kc_band && <Band band={result.kc_band} label={t("check.part")} />}
            {result.next_kc && <span>{t("chat.suggestedNext")} <strong>{result.next_kc.name}</strong></span>}
          </div>
        </div>
      )}
    </form>
  );
}
