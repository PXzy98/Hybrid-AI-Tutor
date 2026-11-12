import { useQuery } from "@tanstack/react-query";
import { GraduationCap, KeyRound, MessageSquarePlus, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, NavLink, Outlet, useMatch, useNavigate, useSearchParams } from "react-router-dom";

import { api, type Me } from "@/api/endpoints";
import { roleIn, useCourses, useResetSession } from "@/auth";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { LanguageSwitch, useI18n } from "@/i18n";
import { cn } from "@/lib/utils";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ErrorNote, ThemeToggle } from "./common";
import ErrorBoundary from "./ErrorBoundary";

// course types are the privacy profiles of the backend (backend/app/privacy/profiles)
const COURSE_TYPES = ["general", "ece", "life_science", "medical_science"];

const linkClass = ({ isActive }: { isActive: boolean }) =>
  cn("block truncate rounded-md px-3 py-1.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring",
    isActive ? "bg-accent font-medium text-accent-foreground" : "hover:bg-muted");

/** Header, left sidebar (courses, and for the open course its modules and the student's conversations) and the page. */
export default function AppShell({ me }: { me: Me }) {
  const navigate = useNavigate();
  const resetSession = useResetSession();
  const { t } = useI18n();
  const courses = useCourses();
  const match = useMatch("/courses/:courseId/*");
  const courseId = match ? Number(match.params.courseId) : null;
  const current = courses.data?.find((c) => c.id === courseId);
  const isStudent = !!current && roleIn(current, me) === "student";
  const showSidebar = !me.must_change_password;

  async function logout() {
    await api.logout().catch(() => undefined);
    resetSession(null);
    navigate("/login", { replace: true });
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b bg-card">
        <div className="flex flex-wrap items-center gap-2 px-4 py-2">
          <Link to="/courses" className="mr-4 flex items-center gap-2 font-semibold text-primary">
            <GraduationCap aria-hidden className="size-5" />{t("app.name")}
          </Link>
          <div className="ml-auto flex items-center gap-2 text-sm text-muted-foreground">
            <LanguageSwitch />
            <ThemeToggle />
            <span>{me.display_name}</span>
            <Button type="button" variant="outline" size="sm" onClick={logout}>{t("nav.logout")}</Button>
          </div>
        </div>
      </header>
      <div className="flex flex-1 flex-col md:flex-row">
        {showSidebar && (
          <aside aria-label={t("nav.main")} className="w-full shrink-0 space-y-5 border-b bg-card/60 p-4 md:w-64 md:border-r md:border-b-0">
            <nav aria-label={t("nav.courses")} className="space-y-1">
              <h2 className="px-3 text-xs font-semibold tracking-wide text-muted-foreground uppercase">{t("nav.courses")}</h2>
              {courses.data?.map((c) => (
                <NavLink key={c.id} to={`/courses/${c.id}`} className={() => linkClass({ isActive: c.id === courseId })}>
                  <span className="font-medium">{c.code}</span> <span className="text-muted-foreground">{c.title}</span>
                </NavLink>
              ))}
              {courses.data?.length === 0 && <p className="px-3 text-sm text-muted-foreground">{t("nav.noCourses")}</p>}
              <div className="flex flex-wrap gap-2 px-1 pt-2">
                <Button asChild variant="outline" size="sm"><Link to="/join"><KeyRound aria-hidden />{t("nav.join")}</Link></Button>
                {me.system_role !== "student" && <NewCourse />}
              </div>
            </nav>
            {current && courseId !== null && <CourseNav courseId={courseId} student={isStudent} />}
          </aside>
        )}
        <main className="mx-auto w-full max-w-6xl min-w-0 flex-1 px-4 py-6">
          <ErrorBoundary><Outlet /></ErrorBoundary>
        </main>
      </div>
      <footer role="note" className="border-t border-amber-200 bg-amber-50 py-2 text-center text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100">
        {t("app.disclaimer")}
      </footer>
    </div>
  );
}

/** Modules (pick one to scope the chat) and past conversations of the open course. */
function CourseNav({ courseId, student }: { courseId: number; student: boolean }) {
  const { t } = useI18n();
  const [params, setParams] = useSearchParams();
  const modules = useQuery({ queryKey: ["modules", courseId], queryFn: () => api.modules(courseId) });
  const conversations = useQuery({ queryKey: ["conversations", courseId], queryFn: () => api.conversations(courseId), enabled: student });
  const activeModule = params.get("module");
  const activeConversation = params.get("c");
  const chatPath = `/courses/${courseId}/chat`;
  const navigate = useNavigate();
  function open(next: Record<string, string | null>) {
    const search = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) v === null ? search.delete(k) : search.set(k, v);
    if (student) navigate({ pathname: chatPath, search: search.toString() });
    else setParams(search);
  }
  return (
    <>
      <nav aria-label={t("nav.modules")} className="space-y-1">
        <h2 className="px-3 text-xs font-semibold tracking-wide text-muted-foreground uppercase">{t("nav.modules")}</h2>
        {student && (
          <button type="button" className={cn(linkClass({ isActive: !activeModule }), "w-full text-left")} onClick={() => open({ module: null })}>
            {t("nav.wholeCourse")}
          </button>
        )}
        {modules.data?.map((m) => student ? (
          <button key={m.id} type="button" className={cn(linkClass({ isActive: activeModule === String(m.id) }), "w-full text-left")}
                  aria-current={activeModule === String(m.id) ? "true" : undefined} onClick={() => open({ module: String(m.id) })}>
            {m.title}
          </button>
        ) : <p key={m.id} className="truncate px-3 py-1.5 text-sm">{m.title}</p>)}
        {modules.data?.length === 0 && <p className="px-3 text-sm text-muted-foreground">{t("nav.noModules")}</p>}
      </nav>
      {student && (
        <nav aria-label={t("nav.conversations")} className="space-y-1">
          <h2 className="px-3 text-xs font-semibold tracking-wide text-muted-foreground uppercase">{t("nav.conversations")}</h2>
          <Button type="button" variant="outline" size="sm" className="mx-1" onClick={() => open({ c: null })}>
            <MessageSquarePlus aria-hidden />{t("nav.newChat")}
          </Button>
          {conversations.data?.map((c) => (
            <button key={c.conversation_id} type="button"
                    className={cn(linkClass({ isActive: activeConversation === c.conversation_id }), "w-full text-left")}
                    onClick={() => open({ c: c.conversation_id })}>
              {new Date(c.last_at).toLocaleDateString()} · {t("nav.turns", { n: c.turns })}
            </button>
          ))}
        </nav>
      )}
    </>
  );
}

/** Create a course: the creator becomes its instructor. */
function NewCourse() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ code: "", title: "", course_type: "general", term_label: "" });
  const create = useMutation({
    mutationFn: () => api.createCourse(form),
    onSuccess: async (course) => {
      await qc.invalidateQueries({ queryKey: ["courses"] });
      setOpen(false);
      navigate(`/courses/${course.id}`);
    },
  });
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });
  function submit(e: FormEvent) {
    e.preventDefault();
    create.mutate();
  }
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button type="button" size="sm"><Plus aria-hidden />{t("course.new")}</Button></DialogTrigger>
      <DialogContent>
        <form onSubmit={submit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>{t("course.new")}</DialogTitle>
            <DialogDescription>{t("course.newHint")}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5"><Label htmlFor="nc-code">{t("course.code")}</Label>
            <Input id="nc-code" value={form.code} onChange={set("code")} required /></div>
          <div className="grid gap-1.5"><Label htmlFor="nc-title">{t("course.title")}</Label>
            <Input id="nc-title" value={form.title} onChange={set("title")} required /></div>
          <div className="grid gap-1.5"><Label htmlFor="nc-type">{t("course.type")}</Label>
            <Select id="nc-type" value={form.course_type} onChange={set("course_type")}>
              {COURSE_TYPES.map((c) => <option key={c} value={c}>{c}</option>)}
            </Select></div>
          <div className="grid gap-1.5"><Label htmlFor="nc-term">{t("course.term")}</Label>
            <Input id="nc-term" value={form.term_label} onChange={set("term_label")} /></div>
          <ErrorNote error={create.error} />
          <DialogFooter><Button type="submit" disabled={create.isPending}>{t("course.create")}</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
