import {
  BookOpen, CalendarX, ChartNoAxesColumn, ClipboardList, FileStack, LayoutDashboard, ListChecks, MessageSquare, Settings,
  SlidersHorizontal, Sparkles, UserPlus, Users, type LucideIcon,
} from "lucide-react";

import type { MessageKey } from "@/i18n/en";

/** A section of the course page: its URL segment (/courses/:id/:section), its name and its icon. */
export type Section = { id: string; label: MessageKey; icon: LucideIcon };
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
    { id: "students", label: "tab.students", icon: Users },
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

export const sectionGroups = (student: boolean) => (student ? STUDENT_SECTIONS : INSTRUCTOR_SECTIONS);

/** The section a URL segment names; an unknown or missing one falls back to the first section. */
export function activeSection(student: boolean, tab: string | undefined): Section {
  const all = sectionGroups(student).flatMap((g) => g.sections);
  return all.find((s) => s.id === tab) ?? all[0];
}
