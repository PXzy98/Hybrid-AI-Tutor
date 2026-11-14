import { useId, type ReactNode } from "react";
import { useParams } from "react-router-dom";

import type { Course } from "@/api/endpoints";
import { roleIn, useCourses, useMe } from "@/auth";
import { ErrorNote } from "@/components/common";
import { useI18n } from "@/i18n";
import AiAssistant from "./instructor/AiAssistant";
import Content from "./instructor/Content";
import EndOfTerm from "./instructor/EndOfTerm";
import Materials from "./instructor/Materials";
import Members from "./instructor/Members";
import InstructorQuizzes from "./instructor/Quizzes";
import Overview from "./instructor/Overview";
import Settings from "./instructor/Settings";
import Students from "./instructor/Students";
import { activeSection } from "./sections";
import Survey from "./Survey";
import Chat from "./student/Chat";
import StudentQuizzes from "./student/Quizzes";
import Progress from "./student/Progress";
import Start from "./student/Start";

/** The course page: the student dashboard or the instructor dashboard, by the role the server reports. The sidebar
 *  links to the sections (pages/sections.ts); the h1 is in the top bar. */
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

function sectionNode(course: Course, student: boolean, id: string): ReactNode {
  if (student) {
    switch (id) {
      case "progress": return <Progress course={course} />;
      case "start": return <Start course={course} />;
      case "quizzes": return <StudentQuizzes course={course} />;
      case "survey": return <Survey course={course} student />;
      default: return null;  // chat is always mounted, see below
    }
  }
  switch (id) {
    case "overview": return <Overview course={course} />;
    case "students": return <Students course={course} />;
    case "content": return <Content course={course} />;
    case "members": return <Members course={course} />;
    case "ai": return <AiAssistant course={course} />;
    case "materials": return <Materials course={course} />;
    case "settings": return <Settings course={course} />;
    case "endterm": return <EndOfTerm course={course} />;
    case "quizzes": return <InstructorQuizzes course={course} />;
    case "survey": return <Survey course={course} student={false} />;
    default: return null;
  }
}

function Dashboard({ course, student, tab }: { course: Course; student: boolean; tab?: string }) {
  const { t } = useI18n();
  const active = activeSection(student, tab);
  const headingId = useId();
  const chatActive = student && active.id === "chat";
  return (
    <>
      {/* a running answer and the live messages live in Chat's state: keep it mounted, hidden, on other sections */}
      {student && (
        <section aria-labelledby={chatActive ? headingId : undefined} hidden={!chatActive}>
          {chatActive && <h2 id={headingId} className="sr-only">{t("tab.chat")}</h2>}
          <Chat course={course} />
        </section>
      )}
      {!chatActive && (
        <section key={active.id} aria-labelledby={headingId}>
          <h2 id={headingId} className="sr-only">{t(active.label)}</h2>
          {sectionNode(course, student, active.id)}
        </section>
      )}
    </>
  );
}
