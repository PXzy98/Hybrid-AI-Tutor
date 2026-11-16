import type { AskResponse } from "@/api/endpoints";
import { useI18n } from "@/i18n";

/** The course material an answer cites. The API returns no passage text, so there is no preview. */
export default function Sources({ sources }: { sources: NonNullable<AskResponse["sources"]> }) {
  const { t } = useI18n();
  return (
    <div>
      <p className="mb-1.5 text-xs font-medium text-muted-foreground">{t("chat.sources")}</p>
      <ul className="flex flex-wrap gap-2">
        {sources.map((s, i) => (
          <li key={`${s.source}:${s.title}:${i}`}
              className="flex max-w-64 min-w-0 items-start gap-2 rounded-lg border bg-card px-2.5 py-1.5 text-xs">
            <span aria-hidden className="mt-px flex size-4 shrink-0 items-center justify-center rounded bg-muted text-[0.625rem] font-semibold tabular-nums text-muted-foreground">
              {i + 1}
            </span>
            <span className="min-w-0">
              <span className="sr-only">[{i + 1}] </span>
              <span className="line-clamp-2 font-medium">{s.title}</span>
              <span className="block truncate text-muted-foreground">{s.source}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
