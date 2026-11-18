import { ArrowRight, GraduationCap, KeyRound } from "lucide-react";
import { Link } from "react-router-dom";

import { useCourses, useMe } from "@/auth";
import { EmptyState, ErrorNote, Loading, PageHeader } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n";

/** Landing page after login: the courses the caller can see. */
export default function CoursePicker() {
  const courses = useCourses();
  const { data: me } = useMe();
  const { t } = useI18n();
  const join = (
    <Button asChild variant="outline" size="sm"><Link to="/join"><KeyRound aria-hidden />{t("nav.join")}</Link></Button>
  );
  return (
    <div className="space-y-6">
      <PageHeader level={1} title={t("picker.title")} actions={courses.data?.length ? join : undefined} />
      <ErrorNote error={courses.error} />
      {courses.isLoading && <Loading variant="cards" />}
      {courses.data?.length === 0 && (
        <EmptyState icon={GraduationCap} title={t("picker.emptyTitle")} action={join}>{t("picker.empty")}</EmptyState>
      )}
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {courses.data?.map((c) => (
          <li key={c.id}>
            <Link to={`/courses/${c.id}`}
                  className="group flex h-full flex-col gap-3 rounded-xl border bg-card p-4 transition-colors outline-hidden hover:border-foreground/20 hover:bg-accent/40 focus-visible:ring-2 focus-visible:ring-ring">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="text-sm font-semibold">{c.code}</h3>
                  <p className="mt-0.5 text-sm text-muted-foreground">{c.title}</p>
                </div>
                <ArrowRight aria-hidden
                  className="mt-0.5 size-4 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" />
              </div>
              <div className="mt-auto flex flex-wrap gap-1.5">
                <Badge variant="secondary">{c.my_role ? t(`role.${c.my_role}`) : me ? t(`role.${me.system_role}`) : ""}</Badge>
                {c.term_label && <Badge variant="outline">{c.term_label}</Badge>}
                {c.status === "archived" && <Badge variant="warning">{t("course.archived")}</Badge>}
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
