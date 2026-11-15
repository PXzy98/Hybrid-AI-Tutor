import { BrandMark } from "@/components/shell/Sidebar";
import { useI18n } from "@/i18n";

/** A new conversation: a title, the existing invitation sentence and three suggestions that fill the composer
 *  (they do not send). */
export default function EmptyChat({ onSuggest }: { onSuggest: (text: string) => void }) {
  const { t } = useI18n();
  const suggestions = [t("chat.suggest1"), t("chat.suggest2"), t("chat.suggest3")];
  return (
    <div className="animate-in-fade flex min-h-[45vh] flex-col items-center justify-center gap-3 py-8 text-center">
      <BrandMark className="size-10" />
      <p className="text-xl font-semibold tracking-tight">{t("chat.emptyTitle")}</p>
      <p className="text-sm text-muted-foreground">{t("chat.empty")}</p>
      <div role="group" aria-label={t("chat.suggested")} className="mt-4 grid w-full gap-2 sm:grid-cols-3">
        {suggestions.map((s) => (
          <button key={s} type="button" onClick={() => onSuggest(s)}
                  className="rounded-xl border bg-card p-3 text-left text-sm transition-colors outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring">
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
