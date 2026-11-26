import { useId, type ReactNode } from "react";
import { BookX, FileQuestion } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import type { Course } from "@/api/endpoints";
import { roleIn, useCourses, useMe } from "@/auth";
import { EmptyState, ErrorNote, Loading } from "@/components/common";
import PrivacyNotice from "@/components/PrivacyNotice";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n";
import InstructorAnnouncements, { StudentAnnouncements } from "./Announcements";
import AiAssistant from "./instructor/AiAssistant";
import Content from "./instructor/Content";
import EndOfTerm from "./instructor/EndOfTerm";
import Materials from "./instructor/Materials";
import Members from "./instructor/Members";
import InstructorQuizzes from "./instructor/Quizzes";
import Overview from "./instructor/Overview";
import Settings from "./instructor/Settings";
import Students from "./instructor/Students";
import { activeSection, isKnownSection } from "./sections";
import Survey from "./Survey";
import { useDocumentTitle } from "@/lib/useDocumentTitle";
import Chat from "./student/chat/Chat";
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
  if (courses.isLoading || !me) return <Loading variant="list" />;
  if (courses.isError) return <ErrorNote error={courses.error} />;
  const course = courses.data?.find((c) => c.id === id);
  if (!course) {
    return (
      <EmptyState icon={BookX} title={t("course.notFoundTitle")}
                  action={<Button asChild variant="outline"><Link to="/courses">{t("course.backToCourses")}</Link></Button>}>
        {t("course.notFound")}
      </EmptyState>
    );
  }
  return <Dashboard course={course} student={roleIn(course, me) === "student"} tab={tab} />;
}

function sectionNode(course: Course, student: boolean, id: string): ReactNode {
  if (student) {
    switch (id) {
      case "announcements": return <StudentAnnouncements course={course} />;
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
    case "announcements": return <InstructorAnnouncements course={course} />;
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
  const active = activeSection(student, tab, course.individual_view);
  const headingId = useId();
  const unknown = !isKnownSection(student, tab);
  useDocumentTitle(t(unknown ? "page.notFoundTitle" : active.label), course.code);
  const chatActive = student && active.id === "chat" && !unknown;
  return (
    <>
      {student && <PrivacyNotice key={course.id} course={course} />}
      {/* a running answer and the live messages live in Chat's state: keep it mounted, hidden, on other sections */}
      {student && (
        <section aria-labelledby={chatActive ? headingId : undefined} hidden={!chatActive}>
          {chatActive && <h2 id={headingId} className="sr-only">{t("tab.chat")}</h2>}
          <Chat course={course} />
        </section>
      )}
      {/* a mistyped section: the chat above stays mounted, hidden, so a running answer is not lost */}
      {unknown && (
        <EmptyState icon={FileQuestion} title={t("page.notFoundTitle")}
                    action={<Button asChild variant="outline"><Link to={`/courses/${course.id}`}>{t("page.backToCourse")}</Link></Button>}>
          {t("page.notFound")}
        </EmptyState>
      )}
      {!chatActive && !unknown && (
        <section key={active.id} aria-labelledby={headingId}>
          {/* My progress shows its own visible heading: a second, hidden one would read twice */}
          {active.id === "progress" && student
            ? <span id={headingId} className="sr-only">{t(active.label)}</span>
            : <h2 id={headingId} className="sr-only">{t(active.label)}</h2>}
          {sectionNode(course, student, active.id)}
        </section>
      )}
    </>
  );
}
