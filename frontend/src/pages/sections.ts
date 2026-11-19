import {
  BookOpen, CalendarX, ChartNoAxesColumn, ClipboardList, FileStack, LayoutDashboard, ListChecks, MessageSquare, Settings,
  SlidersHorizontal, Sparkles, UserPlus, Users, type LucideIcon,
} from "lucide-react";

import type { MessageKey } from "@/i18n/en";

/** A section of the course page: its URL segment (/courses/:id/:section), its name and its icon. `individual`:
 *  shows one student's data, so it exists only where the deployment allows individual views (v5 V1). */
export type Section = { id: string; label: MessageKey; icon: LucideIcon; individual?: boolean };
export type SectionGroup = { label?: MessageKey; sections: Section[] };

export const STUDENT_SECTIONS: SectionGroup[] = [{
  sections: [
    { id: "chat", label: "tab.chat", icon: MessageSquare },
    { id: "progress", label: "tab.progress", icon: ChartNoAxesColumn },
    { id: "quizzes", label: "tab.quizzes", icon: ListChecks },
    { id: "start", label: "tab.start", icon: SlidersHorizontal },
    { id: "survey", label: "tab.survey", icon: ClipboardList },
  ],
}];

export const INSTRUCTOR_SECTIONS: SectionGroup[] = [
  { label: "nav.group.class", sections: [
    { id: "overview", label: "tab.overview", icon: LayoutDashboard },
    { id: "students", label: "tab.students", icon: Users, individual: true },
  ] },
  { label: "nav.group.teaching", sections: [
    { id: "content", label: "tab.content", icon: BookOpen },
    { id: "materials", label: "tab.materials", icon: FileStack },
    { id: "quizzes", label: "tab.quizzes", icon: ListChecks },
    { id: "ai", label: "tab.ai", icon: Sparkles },
  ] },
  { label: "nav.group.course", sections: [
    { id: "members", label: "tab.members", icon: UserPlus },
    { id: "settings", label: "tab.settings", icon: Settings },
    { id: "survey", label: "tab.survey", icon: ClipboardList },
    { id: "endterm", label: "tab.endterm", icon: CalendarX },
  ] },
];

export const sectionGroups = (student: boolean, individualView = false): SectionGroup[] =>
  (student ? STUDENT_SECTIONS : INSTRUCTOR_SECTIONS)
    .map((g) => ({ ...g, sections: g.sections.filter((s) => individualView || !s.individual) }));

/** The section a URL segment names; an unknown or missing one falls back to the first section. */
export function activeSection(student: boolean, tab: string | undefined, individualView = false): Section {
  const all = sectionGroups(student, individualView).flatMap((g) => g.sections);
  return all.find((s) => s.id === tab) ?? all[0];
}
