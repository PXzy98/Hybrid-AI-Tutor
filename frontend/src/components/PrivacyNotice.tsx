import { ChevronDown, ShieldCheck } from "lucide-react";
import { useState } from "react";

import type { Course } from "@/api/endpoints";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useI18n } from "@/i18n";
import type { MessageKey } from "@/i18n/en";

// courses whose full notice this browser has already shown (a per-browser convenience, no user data)
const SEEN_KEY = "pact.privacyNotice.seen";

function seenCourses(): number[] {
  try {
    const raw = JSON.parse(window.localStorage.getItem(SEEN_KEY) ?? "[]");
    return Array.isArray(raw) ? raw.filter((n) => typeof n === "number") : [];
  } catch {
    return [];
  }
}

function markSeen(courseId: number) {
  try {
    window.localStorage.setItem(SEEN_KEY, JSON.stringify([...new Set([...seenCourses(), courseId])]));
  } catch {
    // storage blocked: the full notice shows again next time
  }
}

const POINTS: MessageKey[] = ["privacy.point.private", "privacy.point.instructor", "privacy.point.cloud", "privacy.point.control"];

/** v5 V3: the student's privacy in the course. A short line is always shown at the top of the student pages; the
 *  full notice is open on the first visit of a course and can be opened again from the line. The text matches what
 *  the backend allows: with individual views off (V1) nobody, not even the instructor, sees one student's data. */
export default function PrivacyNotice({ course }: { course: Course }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(() => !seenCourses().includes(course.id));
  const statisticsOnly = !course.individual_view;
  function toggle(next: boolean) {
    setOpen(next);
    if (!next) markSeen(course.id);
  }
  return (
    <Collapsible open={open} onOpenChange={toggle}
                 className="mb-3 rounded-lg border border-success/30 bg-success-soft/60 px-3 py-2 text-sm" aria-label={t("privacy.title")}
                 role="region">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <ShieldCheck aria-hidden className="size-4 shrink-0 text-success" />
        <p className="min-w-0 flex-1">{t(statisticsOnly ? "privacy.line" : "privacy.lineIndividual")}</p>
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
              <li key={key}>{t(key === "privacy.point.instructor" && !statisticsOnly ? "privacy.point.instructorIndividual" : key)}</li>
            ))}
          </ul>
          <Button type="button" size="sm" onClick={() => toggle(false)}>{t("privacy.gotIt")}</Button>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
