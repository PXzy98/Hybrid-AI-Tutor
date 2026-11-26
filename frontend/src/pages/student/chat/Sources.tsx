import type { AskResponse } from "@/api/endpoints";
import { useI18n } from "@/i18n";

/** The file name of a source without its internal folder path; a web address stays whole. */
export function sourceLabel(source: string): string {
  return /^https?:\/\//i.test(source) ? source : source.split(/[\\/]/).pop() || source;
}

/** A readable title: no file-ordering prefix ("01 lecture 1", "10_intro"), underscores as spaces, a capital first
 *  letter when the title has no capital at all (a title taken from a file name). Only a zero-padded number or one
 *  joined by an underscore counts as such a prefix: section numbers ("2.3 Kirchhoff's laws") and numbers that are
 *  part of the title ("3 phase power", "1.5 V cells") stay. A title that is already clean is unchanged. */
export function sourceTitle(title: string): string {
  let out = title.trim();
  if (!/^https?:\/\//i.test(out)) {
    out = out.replace(/^(?:0\d+[\s._)-]+|\d+_+)(?=\S)/, "").replace(/_+/g, " ").replace(/\s{2,}/g, " ").trim();
    if (out && out === out.toLowerCase()) out = out.charAt(0).toUpperCase() + out.slice(1);
  }
  return out || title;
}

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
              <span className="line-clamp-2 font-medium">{sourceTitle(s.title)}</span>
              {sourceLabel(s.source) !== s.title && <span title={sourceLabel(s.source)} className="block truncate text-muted-foreground">{sourceLabel(s.source)}</span>}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
