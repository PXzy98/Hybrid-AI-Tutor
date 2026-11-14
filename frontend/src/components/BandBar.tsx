import { useI18n } from "@/i18n";
import type { MessageKey } from "@/i18n/en";

// one hue with rising weight, the same order as Band.tsx
const SEGMENT: Record<string, string> = {
  basic: "bg-muted-foreground/25",
  intermediate: "bg-primary/40",
  advanced: "bg-primary/70",
  mastered: "bg-primary",
};

/** One stacked bar for a row of band counts. Counts the API suppressed (null) are not drawn and not estimated:
 *  a row with any hidden count shows no bar. The table next to it stays the accessible data. */
export default function BandBar({ counts, bands }: { counts: Record<string, number | null | undefined>; bands: string[] }) {
  const { t } = useI18n();
  const known = bands.filter((b) => b in counts);
  if (known.some((b) => counts[b] === null)) return <span className="text-xs text-muted-foreground">{t("overview.hidden")}</span>;
  const total = known.reduce((sum, b) => sum + (counts[b] ?? 0), 0);
  if (!total) return null;
  const label = known.map((b) => `${t(`band.${b}` as MessageKey)} ${counts[b] ?? 0}`).join(", ");
  return (
    <div role="img" aria-label={label} className="flex h-2 w-full min-w-24 overflow-hidden rounded-full bg-muted">
      {known.map((b) => {
        const n = counts[b] ?? 0;
        return n ? <span key={b} title={`${t(`band.${b}` as MessageKey)}: ${n}`} className={SEGMENT[b]} style={{ width: `${(n / total) * 100}%` }} /> : null;
      })}
    </div>
  );
}
