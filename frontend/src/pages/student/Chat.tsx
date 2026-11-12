import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Cloud, FileText, Send, ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api, type AskResponse, type Course, type CourseProfile } from "@/api/endpoints";
import Band from "@/components/Band";
import CheckCard from "@/components/CheckCard";
import { ErrorNote } from "@/components/common";
import Markdown from "@/components/Markdown";
import RoutingProgress, { type RoutingTrace } from "@/components/RoutingProgress";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Textarea } from "@/components/ui/textarea";
import { useI18n } from "@/i18n";

type Message =
  | { role: "student"; text: string }
  | { role: "tutor"; reply: AskResponse }
  | { role: "history"; text: string }
  | { role: "error"; error: unknown }
  | { role: "routing"; trace: RoutingTrace };

type SendInput = { question: string; traceId: string };

/** Students cannot read the course settings, so the notice is shown unless the course is known to be local-only. */
const COURSE_KNOWN_LOCAL_ONLY = false;

export default function Chat({ course }: { course: Course }) {
  const [params] = useSearchParams();
  const conversationId = params.get("c");
  const moduleParam = params.get("module");
  return <ChatPane key={`${course.id}:${conversationId ?? "new"}`} course={course} initialConversation={conversationId}
                   moduleId={moduleParam ? Number(moduleParam) : null} />;
}

function ChatPane({ course, initialConversation, moduleId }: { course: Course; initialConversation: string | null; moduleId: number | null }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversation, setConversation] = useState<string | null>(initialConversation);
  const [partial, setPartial] = useState("");
  const [question, setQuestion] = useState("");
  const controller = useRef<AbortController | null>(null);
  const traceSequence = useRef(0);
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => () => controller.current?.abort(), []);

  const modules = useQuery({ queryKey: ["modules", course.id], queryFn: () => api.modules(course.id) });
  const profile = useQuery({ queryKey: ["profile", course.id], queryFn: () => api.profile(course.id) });
  const history = useQuery({
    queryKey: ["conversation", course.id, initialConversation],
    queryFn: () => api.conversation(course.id, initialConversation as string),
    enabled: !!initialConversation,
  });
  useEffect(() => {
    if (history.data) setMessages(history.data.turns.map((x) => x.role === "student" ? { role: "student", text: x.text } : { role: "history", text: x.text }));
  }, [history.data]);
  const scope = modules.data?.find((m) => m.id === moduleId);

  const updateTrace = (id: string, patch: Partial<RoutingTrace>, event?: RoutingTrace["events"][number]) =>
    setMessages((prev) => prev.map((m) => m.role === "routing" && m.trace.id === id
      ? { ...m, trace: { ...m.trace, ...patch, events: event ? [...m.trace.events, event] : patch.events ?? m.trace.events } }
      : m));

  const ask = useMutation({
    mutationFn: (input: SendInput) => {
      controller.current = new AbortController();
      setPartial("");
      return api.askStream(course.id, {
        question: input.question, module_id: moduleId, language: "en",
        ...(conversation ? { conversation_id: conversation } : {}),
      }, (event) => {
        if (event.type === "meta") updateTrace(input.traceId, { visible: event.data.show_progress, method: event.data.method });
        if (event.type === "progress") updateTrace(input.traceId, {}, event.data);
        if (event.type === "token") setPartial((p) => p + (event.data.text ?? ""));
        if (event.type === "result") updateTrace(input.traceId, { details: event.data.routing_details, events: event.data.routing_progress ?? [] });
      }, controller.current.signal);
    },
    onSuccess: (reply, input) => {
      setPartial("");
      updateTrace(input.traceId, { running: false, finishedAt: Date.now(), details: reply.routing_details });
      setConversation(reply.conversation_id);
      setMessages((prev) => [...prev, { role: "tutor", reply }]);
      qc.invalidateQueries({ queryKey: ["conversations", course.id] });
    },
    onError: (error, input) => {
      setPartial("");
      updateTrace(input.traceId, { running: false, finishedAt: Date.now(), error: (error as Error).message });
      setMessages((prev) => [...prev, { role: "error", error }]);
    },
  });

  useEffect(() => {
    // a block body on purpose: in some browsers scrollIntoView returns a Promise, which must not be
    // returned to React as if it were a cleanup function
    endRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages.length, partial]);

  function send(e: FormEvent | { preventDefault: () => void }) {
    e.preventDefault();
    const q = question.trim();
    if (!q || ask.isPending) return;
    const traceId = `routing-${++traceSequence.current}`;
    setMessages((prev) => [...prev, { role: "student", text: q },
      { role: "routing", trace: { id: traceId, method: "", visible: true, events: [], running: true, startedAt: Date.now() } }]);
    setQuestion("");
    ask.mutate({ question: q, traceId });
  }

  const lastTutor = [...messages].reverse().find((m) => m.role === "tutor") as { role: "tutor"; reply: AskResponse } | undefined;
  const suggestions = [t("chat.suggest1"), t("chat.suggest2"), t("chat.suggest3")];

  return (
    <div className="flex flex-col gap-4">
      <VisibilityBanner course={course} profile={profile.data} />
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <span>{t("chat.scope")}</span>
        <Badge variant="secondary">{scope ? scope.title : t("nav.wholeCourse")}</Badge>
        {lastTutor?.reply.kc_level && <Band band={lastTutor.reply.kc_level} label={t("chat.levelLabel")} />}
      </div>
      {profile.data && !profile.data.personalized && (
        <Alert variant="info">
          {t("chat.notPersonalized")} <Link to={`/courses/${course.id}/start`} className="underline">{t("chat.personalizeLink")}</Link>
        </Alert>
      )}
      <section aria-label={t("chat.conversation")} aria-live="polite" className="flex min-h-[40vh] flex-col gap-4">
        {history.isLoading && <p className="text-muted-foreground">{t("app.loading")}</p>}
        <ErrorNote error={history.error} />
        {messages.length === 0 && !history.isLoading && <p className="text-muted-foreground">{t("chat.empty")}</p>}
        {messages.map((m, i) =>
          m.role === "student" ? (
            <div key={i} className="max-w-[80%] self-end rounded-2xl bg-primary px-4 py-2 text-primary-foreground">{m.text}</div>
          ) : m.role === "routing" ? (
            m.trace.visible ? <RoutingPanel key={m.trace.id} trace={m.trace} /> : null
          ) : m.role === "error" ? (
            <div key={i} className="max-w-[90%]"><ErrorNote error={m.error} /></div>
          ) : m.role === "history" ? (
            <article key={i} className="max-w-[90%] rounded-2xl border bg-card px-4 py-3 shadow-sm"><Markdown>{m.text}</Markdown></article>
          ) : (
            <TutorMessage key={i} reply={m.reply} courseId={course.id} />
          ),
        )}
        {ask.isPending && partial && (
          <article className="max-w-[90%] rounded-2xl border bg-card px-4 py-3 shadow-sm"><Markdown>{partial}</Markdown></article>
        )}
        {ask.isPending && !partial && <p className="text-sm text-muted-foreground">{t("chat.thinking")}</p>}
        <div ref={endRef} />
      </section>

      {messages.length === 0 && !history.isLoading && (
        <div className="flex flex-wrap gap-2" role="group" aria-label={t("chat.suggested")}>
          {suggestions.map((s) => (
            <Button key={s} type="button" variant="outline" size="sm" onClick={() => setQuestion(s)}>{s}</Button>
          ))}
        </div>
      )}
      <form onSubmit={send} className="sticky bottom-0 flex flex-col gap-2 rounded-2xl border bg-card p-3 shadow-sm">
        {!COURSE_KNOWN_LOCAL_ONLY && <CloudNotice />}
        <label htmlFor="question" className="sr-only">{t("chat.question")}</label>
        <div className="flex gap-2">
          <Textarea id="question" rows={2} className="resize-y border-0 shadow-none focus-visible:ring-0" placeholder={t("chat.placeholder")}
                    value={question} onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) send(e); }} />
          <Button type="submit" className="self-end" disabled={!question.trim() || ask.isPending}>
            <Send aria-hidden />{t("chat.send")}
          </Button>
        </div>
      </form>
    </div>
  );
}

/** T8: the student is told before sending that a cloud model may see the (filtered) question. */
export function CloudNotice() {
  const { t, lang } = useI18n();
  return (
    <div role="note" className="space-y-1 rounded-lg bg-muted/60 px-3 py-2 text-xs text-muted-foreground">
      <p><Cloud aria-hidden className="mr-1 inline size-3.5" />{t("chat.cloudNotice")}</p>
      {lang !== "en" && <p>{t("chat.englishOnly")}</p>}
    </div>
  );
}

/** Mode B and not yet acknowledged: the student decides before the instructor can see anything. */
function VisibilityBanner({ course, profile }: { course: Course; profile?: CourseProfile }) {
  const { t } = useI18n();
  const v = profile?.visibility;
  if (!v || v.mode !== "B" || v.acknowledged || v.opted_out) return null;
  return (
    <Alert variant="warning" role="status">
      {t("chat.visibilityPending")} <Link to={`/courses/${course.id}/progress`} className="font-medium underline">{t("chat.visibilityLink")}</Link>
    </Alert>
  );
}

/** The routing steps of one answer, collapsed by default. */
function RoutingPanel({ trace }: { trace: RoutingTrace }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  return (
    <Collapsible open={open} onOpenChange={setOpen} className="max-w-2xl">
      <CollapsibleTrigger className="flex items-center gap-1 rounded-md text-xs text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring">
        <ChevronRight aria-hidden className={`size-3.5 transition-transform ${open ? "rotate-90" : ""}`} />
        {t("chat.routingSteps")}{trace.running ? ` · ${t("routing.running")}` : ""}
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-2"><RoutingProgress trace={trace} /></CollapsibleContent>
    </Collapsible>
  );
}

function TutorMessage({ reply, courseId }: { reply: AskResponse; courseId: number }) {
  const { t } = useI18n();
  const local = reply.route_target === "local";
  return (
    <article className="max-w-[90%] rounded-2xl border bg-card px-4 py-3 shadow-sm">
      <div className="mb-2">
        <Badge variant={local ? "success" : "warning"} title={t(local ? "chat.localHint" : "chat.cloudHint")} data-route={reply.route_target}>
          {local ? <ShieldCheck aria-hidden /> : <Cloud aria-hidden />}
          {t(local ? "chat.local" : "chat.cloud")}
        </Badge>
      </div>
      <Markdown>{reply.answer}</Markdown>
      {!!reply.warnings?.length && (
        <ul className="mt-2 space-y-0.5 text-xs text-amber-800 dark:text-amber-300">
          {reply.warnings.map((w) => <li key={w}>⚠ {w}</li>)}
        </ul>
      )}
      {!!reply.sources?.length && (
        <div className="mt-3">
          <p className="mb-1 text-xs font-medium text-muted-foreground">{t("chat.sources")}</p>
          <ul className="flex flex-wrap gap-2">
            {reply.sources.map((s, i) => (
              <li key={`${s.source}:${s.title}:${i}`} title={`${s.title} (${s.source})`}
                  className="flex max-w-60 items-start gap-1.5 rounded-md border bg-muted/40 px-2 py-1 text-xs">
                <FileText aria-hidden className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
                <span className="min-w-0"><span className="block truncate font-medium">[{i + 1}] {s.title}</span>
                  <span className="block truncate text-muted-foreground">{s.source}</span></span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {reply.next_kc && (
        <p className="mt-2 text-xs text-muted-foreground">{t("chat.suggestedNext")} <strong>{reply.next_kc.name}</strong></p>
      )}
      {reply.check_item && <CheckCard courseId={courseId} item={reply.check_item} />}
    </article>
  );
}
