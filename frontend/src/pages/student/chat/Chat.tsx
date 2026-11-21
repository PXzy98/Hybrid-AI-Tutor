import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { api, type AskResponse, type Course, type CourseProfile } from "@/api/endpoints";
import Band from "@/components/Band";
import type { RoutingTrace } from "@/components/RoutingProgress";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { useI18n } from "@/i18n";
import { LatestAnnouncements } from "../../Announcements";
import Composer, { CloudNotice } from "./Composer";
import MessageList, { type Message } from "./MessageList";

export { CloudNotice };

type SendInput = { question: string; traceId: string };

const isAbort = (error: unknown) => error instanceof DOMException && error.name === "AbortError";

export default function Chat({ course }: { course: Course }) {
  const [params, setParams] = useSearchParams();
  const conversationId = params.get("c");
  const moduleParam = params.get("module");
  // The pane is rebuilt when the sidebar changes `c` (a past conversation, or New chat). A conversation the pane
  // itself starts is written to the URL, and must not rebuild it.
  const shown = useRef<string | null>(conversationId);
  const [epoch, setEpoch] = useState(0);
  // New chat also while `c` is already empty (the first answer of a conversation is still streaming): the sidebar
  // sends a new stamp in the router state
  const location = useLocation();
  const newChat = (location.state as { newChat?: number } | null)?.newChat;
  const newChatSeen = useRef(newChat);
  const asked = newChat !== undefined && newChat !== newChatSeen.current;
  newChatSeen.current = newChat ?? newChatSeen.current;
  if (conversationId !== shown.current || asked) {
    shown.current = conversationId;
    setEpoch((e) => e + 1);
  }
  // V8: "Explain it another way" on My progress hands over a prepared request (router state, never the URL);
  // it fills the input of a new conversation, the student still decides to send it
  const navigate = useNavigate();
  const ask = (location.state as { ask?: string } | null)?.ask;
  const [prefill, setPrefill] = useState<{ text: string; n: number } | null>(null);
  const prefillUsed = useCallback(() => setPrefill(null), []);  // once in the composer, not again in a new pane
  useEffect(() => {
    if (!ask) return;
    setPrefill((p) => ({ text: ask, n: (p?.n ?? 0) + 1 }));
    navigate({ pathname: location.pathname, search: location.search }, { replace: true, state: null });
  }, [ask, location.pathname, location.search, navigate]);
  const started = (id: string) => {
    shown.current = id;
    setParams((prev) => { const next = new URLSearchParams(prev); next.set("c", id); return next; }, { replace: true });
  };
  return <ChatPane key={`${course.id}:${epoch}`} course={course} initialConversation={shown.current}
                   moduleId={moduleParam ? Number(moduleParam) : null} onStarted={started} prefill={prefill}
                   onPrefillUsed={prefillUsed} />;
}

function ChatPane({ course, initialConversation: initial, moduleId, onStarted, prefill, onPrefillUsed }: { course: Course; initialConversation: string | null; moduleId: number | null; onStarted: (id: string) => void; prefill?: { text: string; n: number } | null; onPrefillUsed?: () => void }) {
  const [initialConversation] = useState(initial); // fixed for the life of the pane
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversation, setConversation] = useState<string | null>(initialConversation);
  const [partial, setPartial] = useState("");
  const [question, setQuestion] = useState("");
  useEffect(() => {
    if (!prefill) return;
    setQuestion(prefill.text);
    onPrefillUsed?.();
  }, [prefill, onPrefillUsed]);
  const controller = useRef<AbortController | null>(null);
  const traceSequence = useRef(0);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => () => controller.current?.abort(), []);

  const modules = useQuery({ queryKey: ["modules", course.id], queryFn: () => api.modules(course.id) });
  const profile = useQuery({ queryKey: ["profile", course.id], queryFn: () => api.profile(course.id) });
  const history = useQuery({
    queryKey: ["conversation", course.id, initialConversation, lang],
    queryFn: () => api.conversation(course.id, initialConversation as string, lang),
    enabled: !!initialConversation,
    staleTime: Infinity, refetchOnWindowFocus: false, refetchOnReconnect: false,
  });
  // the stored history is loaded once per conversation; a later refetch must not overwrite live messages
  const hydrated = useRef(false);
  useEffect(() => {
    if (!history.data || hydrated.current) return;
    hydrated.current = true;
    const past: Message[] = history.data.turns.map((x) => x.role === "student" ? { role: "student", text: x.text } : { role: "history", text: x.text });
    setMessages((live) => [...past, ...live]);
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
        question: input.question, module_id: moduleId, language: lang,  // fixed notes come back in it
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
      if (!conversation) onStarted(reply.conversation_id);
      setMessages((prev) => [...prev, { role: "tutor", reply }]);
      qc.invalidateQueries({ queryKey: ["conversations", course.id] });
    },
    onError: (error, input) => {
      setPartial("");
      // the student pressed Stop: end quietly, without an error message
      if (isAbort(error)) {
        updateTrace(input.traceId, { running: false, finishedAt: Date.now() });
        return;
      }
      updateTrace(input.traceId, { running: false, finishedAt: Date.now(), error: (error as Error).message });
      setMessages((prev) => [...prev, { role: "error", error, question: input.question }]);
    },
  });

  function submitQuestion(q: string) {
    const traceId = `routing-${++traceSequence.current}`;
    setMessages((prev) => [...prev, { role: "student", text: q },
      { role: "routing", trace: { id: traceId, method: "", visible: true, events: [], running: true, startedAt: Date.now() } }]);
    ask.mutate({ question: q, traceId });
  }

  function send(e: FormEvent | { preventDefault: () => void }) {
    e.preventDefault();
    const q = question.trim();
    if (!q || ask.isPending) return;
    setQuestion("");
    submitQuestion(q);
  }

  // the question is still in this page's memory only (never stored by the browser); sending it again is a new turn
  function retry(q: string) {
    if (!ask.isPending) submitQuestion(q);
  }

  function suggest(text: string) {
    setQuestion(text);
    inputRef.current?.focus();
  }

  const lastTutor = [...messages].reverse().find((m) => m.role === "tutor") as { role: "tutor"; reply: AskResponse } | undefined;
  const scopeLabel = scope ? scope.title : t("nav.wholeCourse");

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
      <VisibilityBanner course={course} profile={profile.data} />
      {profile.data && !profile.data.personalized && (
        <Alert variant="info" icon>
          {t("chat.notPersonalized")} <Link to={`/courses/${course.id}/start`} className="font-medium underline underline-offset-2">{t("chat.personalizeLink")}</Link>
        </Alert>
      )}
      {/* the course home: a new conversation shows the latest announcements (V20) */}
      {!initialConversation && messages.length === 0 && <LatestAnnouncements course={course} />}
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <span>{t("chat.scope")}</span>
        <Badge variant="secondary">{scopeLabel}</Badge>
        {lastTutor?.reply.kc_level && <Band band={lastTutor.reply.kc_level} label={t("chat.levelLabel")} />}
      </div>
      <MessageList courseId={course.id} messages={messages} partial={partial} pending={ask.isPending}
                   loadingHistory={history.isLoading} historyError={history.error} onSuggest={suggest} onRetry={retry}>
        <Composer ref={inputRef} value={question} onChange={setQuestion} onSubmit={send} pending={ask.isPending}
                  onStop={() => controller.current?.abort()} scopeLabel={scopeLabel} localOnly={!!course.local_only} />
      </MessageList>
    </div>
  );
}

/** Mode B and not yet acknowledged: the student decides before the instructor can see anything. */
function VisibilityBanner({ course, profile }: { course: Course; profile?: CourseProfile }) {
  const { t } = useI18n();
  const v = profile?.visibility;
  if (!v || v.mode !== "B" || v.acknowledged || v.opted_out) return null;
  return (
    <Alert variant="warning" role="status" icon>
      {t("chat.visibilityPending")} <Link to={`/courses/${course.id}/progress`} className="font-medium underline underline-offset-2">{t("chat.visibilityLink")}</Link>
    </Alert>
  );
}
