import { ChevronDown, ShieldCheck } from "lucide-react";
import { useState } from "react";

import type { Course } from "@/api/endpoints";
import { useMe } from "@/auth";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useI18n } from "@/i18n";
import type { MessageKey } from "@/i18n/en";

// "<account>:<course>" pairs whose full notice this browser has already shown (a per-browser convenience, ids
// only). Per account, so a new student on a shared computer still sees the full notice first (V17 W22).
const SEEN_KEY = "pact.privacyNotice.seenBy";

function seen(): string[] {
  try {
    const raw = JSON.parse(window.localStorage.getItem(SEEN_KEY) ?? "[]");
    return Array.isArray(raw) ? raw.filter((n) => typeof n === "string") : [];
  } catch {
    return [];
  }
}

function markSeen(pair: string) {
  try {
    window.localStorage.setItem(SEEN_KEY, JSON.stringify([...new Set([...seen(), pair])]));
  } catch {
    // storage blocked: the full notice shows again next time
  }
}

const POINTS: MessageKey[] = ["privacy.point.private", "privacy.point.instructor", "privacy.point.cloud", "privacy.point.control"];

// with individual views on, the points that depend on the student's agreement on My progress
const INDIVIDUAL: Partial<Record<MessageKey, MessageKey>> = {
  "privacy.point.private": "privacy.point.privateIndividual",
  "privacy.point.instructor": "privacy.point.instructorIndividual",
};

/** v5 V3: the student's privacy in the course. A short line is always shown at the top of the student pages; the
 *  full notice is open on the first visit of a course and can be opened again from the line. The text matches what
 *  the backend allows: with individual views off (V1) nobody, not even the instructor, sees one student's data.
 *  Keyed by course where it is used, so switching course starts from that course's first-visit state. */
export default function PrivacyNotice({ course }: { course: Course }) {
  const { t } = useI18n();
  const pair = `${useMe().data?.account_id ?? 0}:${course.id}`;
  const [open, setOpen] = useState(() => !seen().includes(pair));
  const statisticsOnly = !course.individual_view;
  function toggle(next: boolean) {
    setOpen(next);
    if (!next) markSeen(pair);
  }
  return (
    <Collapsible open={open} onOpenChange={toggle}
                 className="mb-3 rounded-lg border border-success/30 bg-success-soft/60 px-3 py-2 text-sm" aria-label={t("privacy.title")}
                 role="region">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <ShieldCheck aria-hidden className="size-4 shrink-0 text-success" />
        {/* basis-48: on a narrow screen the text keeps a readable width and the button wraps below it */}
        <p className="min-w-0 flex-1 basis-48">{t(statisticsOnly ? "privacy.line" : "privacy.lineIndividual")}</p>
        <CollapsibleTrigger asChild>
          <Button type="button" variant="ghost" size="sm" className="h-7 px-2" aria-expanded={open}>
            {t(open ? "privacy.hide" : "privacy.more")}
            <ChevronDown aria-hidden className={open ? "rotate-180 transition-transform" : "transition-transform"} />
          </Button>
        </CollapsibleTrigger>
      </div>
      <CollapsibleContent>
        <div className="space-y-2 pt-2 pb-1">
          <h3 className="font-medium">{t("privacy.title")}</h3>
          <ul className="list-disc space-y-1 pl-5">
            {POINTS.map((key) => (
              <li key={key}>{t(statisticsOnly ? key : INDIVIDUAL[key] ?? key)}</li>
            ))}
          </ul>
          <Button type="button" size="sm" onClick={() => toggle(false)}>{t("privacy.gotIt")}</Button>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
