import { useQuery } from "@tanstack/react-query";
import { SquarePen } from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { api, type Course } from "@/api/endpoints";
import { useI18n } from "@/i18n";
import type { MessageKey } from "@/i18n/en";
import { cn } from "@/lib/utils";
import { activeSection, sectionGroups } from "@/pages/sections";

export const itemClass = (active: boolean) =>
  cn("flex h-9 w-full min-w-0 items-center gap-2.5 rounded-md px-2.5 text-left text-sm outline-hidden transition-colors focus-visible:ring-2 focus-visible:ring-ring [&_svg]:size-4 [&_svg]:shrink-0",
    active ? "bg-primary-soft font-medium text-primary-soft-foreground" : "text-foreground/80 hover:bg-accent hover:text-foreground");

export function GroupLabel({ children }: { children: string }) {
  return <p className="px-2.5 pt-4 pb-1 text-xs font-medium text-muted-foreground">{children}</p>;
}

/** The open course: New chat (students), its sections, its modules (the chat scope) and the student's conversations. */
export default function CourseNav({ course, student, tab }: { course: Course; student: boolean; tab?: string }) {
  const { t } = useI18n();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const courseId = course.id;
  const modules = useQuery({ queryKey: ["modules", courseId], queryFn: () => api.modules(courseId), enabled: student });
  const conversations = useQuery({ queryKey: ["conversations", courseId], queryFn: () => api.conversations(courseId), enabled: student });
  const activeModule = params.get("module");
  const activeConversation = params.get("c");
  const current = activeSection(student, tab);
  const chatPath = `/courses/${courseId}/chat`;

  function open(next: Record<string, string | null>) {
    const search = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) v === null ? search.delete(k) : search.set(k, v);
    if (student) navigate({ pathname: chatPath, search: search.toString() });
    else setParams(search);
  }

  return (
    <>
      {student && (
        <button type="button" onClick={() => open({ c: null })}
                className="mb-1 flex h-9 w-full items-center gap-2.5 rounded-md border bg-background px-2.5 text-sm font-medium shadow-xs outline-hidden transition-colors hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring">
          <SquarePen aria-hidden className="size-4" />{t("nav.newChat")}
        </button>
      )}
      <nav aria-label={t(student ? "dash.student" : "dash.instructor")}>
        {sectionGroups(student).map((group, i) => (
          <div key={group.label ?? i}>
            {group.label && <GroupLabel>{t(group.label)}</GroupLabel>}
            <ul className="space-y-0.5">
              {group.sections.map((s) => (
                <li key={s.id}>
                  <Link to={{ pathname: `/courses/${courseId}/${s.id}`, search: params.toString() }}
                        aria-current={s.id === current.id ? "page" : undefined} className={itemClass(s.id === current.id)}>
                    <s.icon aria-hidden /><span className="truncate">{t(s.label)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
      {student && <nav aria-label={t("nav.modules")}>
        <GroupLabel>{t("nav.modules")}</GroupLabel>
        <div className="space-y-0.5">
          <button type="button" className={itemClass(!activeModule)} onClick={() => open({ module: null })}>
            <span className="truncate">{t("nav.wholeCourse")}</span>
          </button>
          {modules.data?.map((m) => (
            <button key={m.id} type="button" className={itemClass(activeModule === String(m.id))}
                    aria-current={activeModule === String(m.id) ? "true" : undefined} onClick={() => open({ module: String(m.id) })}>
              <span className="truncate">{m.title}</span>
            </button>
          ))}
          {modules.data?.length === 0 && <p className="px-2.5 text-sm text-muted-foreground">{t("nav.noModules")}</p>}
        </div>
      </nav>}
      {student && !!conversations.data?.length && (
        <nav aria-label={t("nav.conversations")}>
          {byDay(conversations.data).map(([label, rows]) => (
            <div key={label}>
              <GroupLabel>{t(label)}</GroupLabel>
              <div className="space-y-0.5">
                {rows.map((c) => (
                  <button key={c.conversation_id} type="button" className={itemClass(activeConversation === c.conversation_id)}
                          aria-current={activeConversation === c.conversation_id ? "true" : undefined}
                          onClick={() => open({ c: c.conversation_id })}>
                    <span className="truncate">{new Date(c.last_at).toLocaleDateString()} · {t("nav.turns", { n: c.turns })}</span>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </nav>
      )}
    </>
  );
}

/** Conversations in Today / Yesterday / Earlier, by the local date of their last message. The API stores no titles. */
function byDay<T extends { last_at: string }>(rows: T[]): [MessageKey, T[]][] {
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  const today = start.getTime();
  const yesterday = today - 86_400_000;
  const groups: [MessageKey, T[]][] = [["nav.today", []], ["nav.yesterday", []], ["nav.earlier", []]];
  for (const row of rows) {
    const at = new Date(row.last_at).getTime();
    groups[at >= today ? 0 : at >= yesterday ? 1 : 2][1].push(row);
  }
  return groups.filter(([, list]) => list.length > 0);
}
