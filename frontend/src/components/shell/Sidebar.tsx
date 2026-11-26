import { GraduationCap, KeyRound, PanelLeft, Settings2 } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import type { Course, Me } from "@/api/endpoints";
import { useCourses } from "@/auth";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { useI18n } from "@/i18n";
import CourseNav, { itemClass } from "./CourseNav";
import NewCourseDialog from "./NewCourseDialog";
import UserMenu from "./UserMenu";

export function BrandMark({ className = "size-7" }: { className?: string }) {
  return (
    <span aria-hidden className={`flex shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground ${className}`}>
      <GraduationCap className="size-[60%]" />
    </span>
  );
}

type Props = { me: Me; current?: Course; student: boolean; tab?: string; onCollapse?: () => void };

/** Brand, course switcher, the open course's navigation and the account menu. Rendered in the desktop aside and
 *  in the mobile sheet. */
export default function Sidebar({ me, current, student, tab, onCollapse }: Props) {
  const { t } = useI18n();
  const courses = useCourses();
  const navigate = useNavigate();
  // by course code, the same way in the switcher and in the list ("MED 0000" before "MIT 6.002")
  const sorted = [...(courses.data ?? [])].sort((a, b) => a.code.localeCompare(b.code, undefined, { numeric: true, sensitivity: "base" }));

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-12 shrink-0 items-center gap-2 px-3">
        <Link to="/courses" className="flex min-w-0 items-center gap-2 rounded-md font-semibold outline-hidden focus-visible:ring-2 focus-visible:ring-ring">
          <BrandMark className="size-6" /><span className="truncate">{t("app.name")}</span>
        </Link>
        {onCollapse && (
          <Tooltip content={t("nav.collapse")} side="right">
            <Button type="button" variant="ghost" size="icon-sm" className="ml-auto text-muted-foreground"
                    aria-label={t("nav.collapse")} aria-expanded onClick={onCollapse}>
              <PanelLeft aria-hidden />
            </Button>
          </Tooltip>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
        <nav aria-label={t("nav.courses")} className="space-y-1 pt-1">
          {current ? (
            <>
              <label htmlFor="course-switch" className="sr-only">{t("nav.courses")}</label>
              <select id="course-switch" value={current.id} title={`${current.code} · ${current.title}`} onChange={(e) => navigate(`/courses/${e.target.value}`)}
                      className="select-chevron h-9 w-full appearance-none truncate rounded-md border border-input bg-background py-1 pr-8 pl-2.5 text-sm font-medium outline-hidden focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/30">
                {sorted.map((c) => <option key={c.id} value={c.id} title={c.title}>{c.code} · {c.title}</option>)}
              </select>
            </>
          ) : (
            <>
              <p className="px-2.5 pb-1 text-xs font-medium text-muted-foreground">{t("nav.courses")}</p>
              {sorted.map((c) => (
                <Link key={c.id} to={`/courses/${c.id}`} className={itemClass(false)} title={`${c.code} · ${c.title}`}>
                  <span className="truncate"><span className="font-medium">{c.code}</span> <span className="text-muted-foreground">{c.title}</span></span>
                </Link>
              ))}
              {courses.data?.length === 0 && <p className="px-2.5 text-sm text-muted-foreground">{t("nav.noCourses")}</p>}
            </>
          )}
          <div className="flex flex-col pt-1">
            <Button asChild variant="ghost" size="sm" className="justify-start text-muted-foreground hover:text-foreground">
              <Link to="/join"><KeyRound aria-hidden />{t("nav.join")}</Link>
            </Button>
            {me.system_role !== "student" && <NewCourseDialog />}
            {me.system_role === "admin" && (
              <Button asChild variant="ghost" size="sm" className="justify-start text-muted-foreground hover:text-foreground">
                <Link to="/admin"><Settings2 aria-hidden />{t("nav.admin")}</Link>
              </Button>
            )}
          </div>
        </nav>
        {current && <div className="mt-3 border-t pt-3"><CourseNav course={current} student={student} tab={tab} /></div>}
      </div>

      <div className="shrink-0 border-t p-2">
        <UserMenu me={me} />
      </div>
    </div>
  );
}
