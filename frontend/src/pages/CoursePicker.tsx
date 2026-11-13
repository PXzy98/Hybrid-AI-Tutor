import { Link } from "react-router-dom";

import { useCourses, useMe } from "@/auth";
import { ErrorNote } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/i18n";

/** Landing page after login: the courses the caller can see. */
export default function CoursePicker() {
  const courses = useCourses();
  const { data: me } = useMe();
  const { t } = useI18n();
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">{t("picker.title")}</h1>
      <ErrorNote error={courses.error} />
      {courses.isLoading && <p className="text-muted-foreground">{t("app.loading")}</p>}
      {courses.data?.length === 0 && (
        <Card>
          <CardHeader><CardTitle>{t("picker.emptyTitle")}</CardTitle><CardDescription>{t("picker.empty")}</CardDescription></CardHeader>
          <CardContent><Button asChild><Link to="/join">{t("nav.join")}</Link></Button></CardContent>
        </Card>
      )}
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {courses.data?.map((c) => (
          <li key={c.id}>
            <Link to={`/courses/${c.id}`} className="block rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring">
              <Card className="h-full transition-colors hover:bg-accent/40">
                <CardHeader>
                  <CardTitle>{c.code}</CardTitle>
                  <CardDescription>{c.title}</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-wrap gap-2">
                  <Badge variant="secondary">{c.my_role ? t(`role.${c.my_role}`) : me ? t(`role.${me.system_role}`) : ""}</Badge>
                  {c.term_label && <Badge variant="outline">{c.term_label}</Badge>}
                  {c.status === "archived" && <Badge variant="warning">{t("course.archived")}</Badge>}
                </CardContent>
              </Card>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
