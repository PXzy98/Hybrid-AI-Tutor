import { Badge } from "@/components/ui/badge";
import { useI18n } from "@/i18n";
import type { MessageKey } from "@/i18n/en";

const STYLES: Record<string, string> = {
  basic: "border-sky-200 bg-sky-50 text-sky-900 dark:border-sky-800 dark:bg-sky-950 dark:text-sky-100",
  intermediate: "border-violet-200 bg-violet-50 text-violet-900 dark:border-violet-800 dark:bg-violet-950 dark:text-violet-100",
  advanced: "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-100",
  mastered: "border-transparent bg-primary text-primary-foreground",
  not_assessed: "border-border bg-muted text-muted-foreground",
};

/** A level or mastery band. Text, not colour alone, carries the meaning. */
export default function Band({ band, label }: { band: string; label?: string }) {
  const { t } = useI18n();
  return (
    <Badge variant="outline" className={`rounded-full px-2.5 ${STYLES[band] ?? STYLES.basic}`}>
      {label ? `${label}: ` : ""}
      {band in STYLES ? t(`band.${band}` as MessageKey) : band}
    </Badge>
  );
}
