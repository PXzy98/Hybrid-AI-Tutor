import { useI18n } from "../i18n";
import type { MessageKey } from "../i18n/en";

const STYLES: Record<string, string> = {
  basic: "bg-sky-50 text-sky-800 ring-sky-200",
  intermediate: "bg-violet-50 text-violet-800 ring-violet-200",
  advanced: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  mastered: "bg-teal-700 text-white ring-teal-700",
};

/** A level or mastery band. Text, not colour alone, carries the meaning. */
export default function Band({ band, label }: { band: string; label?: string }) {
  const { t } = useI18n();
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${STYLES[band] ?? STYLES.basic}`}>
      {label ? `${label}: ` : ""}
      {band in STYLES || band === "not_assessed" ? t(`band.${band}` as MessageKey) : band}
    </span>
  );
}
