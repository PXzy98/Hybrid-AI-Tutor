import { Badge } from "@/components/ui/badge";
import { useI18n } from "@/i18n";
import type { MessageKey } from "@/i18n/en";

// One hue with rising weight, so the order reads at a glance; the band name is always written out.
const STYLES: Record<string, string> = {
  basic: "border-transparent bg-muted text-muted-foreground",
  intermediate: "border-transparent bg-primary-soft text-primary-soft-foreground",
  advanced: "border-primary bg-primary-soft font-semibold text-primary-soft-foreground",
  mastered: "border-transparent bg-primary text-primary-foreground",
  not_assessed: "border-dashed border-input bg-transparent text-muted-foreground",
};

/** A level or mastery band. Text, not colour alone, carries the meaning. */
export default function Band({ band, label }: { band: string; label?: string }) {
  const { t } = useI18n();
  return (
    <Badge variant="outline" className={`px-2.5 ${STYLES[band] ?? STYLES.basic}`}>
      {label ? `${label}: ` : ""}
      {band in STYLES ? t(`band.${band}` as MessageKey) : band}
    </Badge>
  );
}
