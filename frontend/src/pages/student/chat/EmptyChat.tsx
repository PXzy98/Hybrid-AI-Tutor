import { BrandMark } from "@/components/shell/Sidebar";
import { tEnglish, useI18n } from "@/i18n";

/** A new conversation: a title, the existing invitation sentence and three suggestions that fill the composer
 *  (they do not send). */
export default function EmptyChat({ onSuggest }: { onSuggest: (text: string) => void }) {
  const { t } = useI18n();
  // the label follows the interface language; the question that fills the composer stays English (course search
  // and the privacy filter are English; V22 B2)
  const suggestions = (["chat.suggest1", "chat.suggest2", "chat.suggest3"] as const).map((key) => ({ key, label: t(key), text: tEnglish(key) }));
  return (
    <div className="animate-in-fade flex min-h-[45vh] flex-col items-center justify-center gap-3 py-8 text-center">
      <BrandMark className="size-10" />
      <p className="text-xl font-semibold tracking-tight">{t("chat.emptyTitle")}</p>
      <p className="text-sm text-muted-foreground">{t("chat.empty")}</p>
      <div role="group" aria-label={t("chat.suggested")} className="mt-4 grid w-full gap-2 sm:grid-cols-3">
        {suggestions.map((s) => (
          <button key={s.key} type="button" onClick={() => onSuggest(s.text)}
                  className="rounded-xl border bg-card p-3 text-left text-sm transition-colors outline-hidden hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring">
            {s.label}
          </button>
        ))}
      </div>
    </div>
  );
}
