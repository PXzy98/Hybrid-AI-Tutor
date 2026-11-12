import type { ReactNode } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import type { Course } from "@/api/endpoints";
import { roleIn, useCourses, useMe } from "@/auth";
import { ErrorNote } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useI18n } from "@/i18n";
import type { MessageKey } from "@/i18n/en";
import Content from "./instructor/Content";
import EndOfTerm from "./instructor/EndOfTerm";
import Members from "./instructor/Members";
import InstructorQuizzes from "./instructor/Quizzes";
import Overview from "./instructor/Overview";
import Settings from "./instructor/Settings";
import Students from "./instructor/Students";
import Survey from "./Survey";
import Chat from "./student/Chat";
import StudentQuizzes from "./student/Quizzes";
import Progress from "./student/Progress";
import Start from "./student/Start";

type TabDef = { id: string; label: MessageKey; node: ReactNode; keepMounted?: boolean };

/** The course page: the student dashboard or the instructor dashboard, by the role the server reports. */
export default function CourseDashboard() {
  const { courseId, tab } = useParams();
  const id = Number(courseId);
  const courses = useCourses();
  const { data: me } = useMe();
  const { t } = useI18n();
  if (courses.isLoading || !me) return <p className="text-muted-foreground">{t("app.loading")}</p>;
  if (courses.isError) return <ErrorNote error={courses.error} />;
  const course = courses.data?.find((c) => c.id === id);
  if (!course) return <p role="alert" className="text-destructive">{t("course.notFound")}</p>;
  return <Dashboard course={course} student={roleIn(course, me) === "student"} tab={tab} />;
}

function Dashboard({ course, student, tab }: { course: Course; student: boolean; tab?: string }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [search] = useSearchParams();
  const id = course.id;
  const tabs: TabDef[] = student
    ? [
        { id: "chat", label: "tab.chat", node: <Chat course={course} />, keepMounted: true },
        { id: "progress", label: "tab.progress", node: <Progress course={course} /> },
        { id: "start", label: "tab.start", node: <Start course={course} /> },
        { id: "quizzes", label: "tab.quizzes", node: <StudentQuizzes course={course} /> },
        { id: "survey", label: "tab.survey", node: <Survey course={course} student /> },
      ]
    : [
        { id: "overview", label: "tab.overview", node: <Overview course={course} /> },
        { id: "students", label: "tab.students", node: <Students course={course} /> },
        { id: "content", label: "tab.content", node: <Content course={course} /> },
        { id: "members", label: "tab.members", node: <Members course={course} /> },
        { id: "settings", label: "tab.settings", node: <Settings course={course} /> },
        { id: "endterm", label: "tab.endterm", node: <EndOfTerm course={course} /> },
        { id: "quizzes", label: "tab.quizzes", node: <InstructorQuizzes course={course} /> },
        { id: "survey", label: "tab.survey", node: <Survey course={course} student={false} /> },
      ];
  const active = tabs.find((x) => x.id === tab)?.id ?? tabs[0].id;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">{course.code} <span className="font-normal text-muted-foreground">{course.title}</span></h1>
        <Badge variant="secondary">{t(student ? "role.student" : "role.instructor")}</Badge>
        {course.status === "archived" && <Badge variant="warning">{t("course.archived")}</Badge>}
      </div>
      <Tabs value={active} onValueChange={(v) => navigate({ pathname: `/courses/${id}/${v}`, search: search.toString() })}>
        <TabsList aria-label={t(student ? "dash.student" : "dash.instructor")}>
          {tabs.map((x) => <TabsTrigger key={x.id} value={x.id}>{t(x.label)}</TabsTrigger>)}
        </TabsList>
        {tabs.map((x) => (
          <TabsContent key={x.id} value={x.id} forceMount={x.keepMounted ? true : undefined}
                       className={x.keepMounted ? "data-[state=inactive]:hidden" : undefined}>
            {x.node}
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
