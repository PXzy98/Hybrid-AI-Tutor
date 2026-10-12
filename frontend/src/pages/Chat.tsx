import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { api, type AskResponse, type FeedbackAction } from "../api/endpoints";
import Band from "../components/Band";
import CheckCard from "../components/CheckCard";
import TopicPicker from "../components/TopicPicker";

type Message =
  | { role: "student"; text: string }
  | { role: "tutor"; reply: AskResponse }
  | { role: "error"; text: string };

const FEEDBACK: { action: FeedbackAction; label: string }[] = [
  { action: "more_detail", label: "More detail" },
  { action: "shorter", label: "Shorter" },
  { action: "example_first", label: "Example first" },
  { action: "concept_first", label: "Idea first" },
];

export default function Chat() {
  const [topic, setTopic] = useState("high_blood_pressure");
  const [byTopic, setByTopic] = useState<Record<string, { sessionId: string; messages: Message[] }>>({});
  const [question, setQuestion] = useState("");
  const profile = useQuery({ queryKey: ["profile"], queryFn: api.profile });
  const conversation = byTopic[topic] ?? { sessionId: "", messages: [] };
  const endRef = useRef<HTMLDivElement>(null);

  const push = (m: Message, sessionId?: string) =>
    setByTopic((prev) => {
      const cur = prev[topic] ?? { sessionId: "", messages: [] };
      return { ...prev, [topic]: { sessionId: sessionId ?? cur.sessionId, messages: [...cur.messages, m] } };
    });

  const ask = useMutation({
    mutationFn: (q: string) => api.ask({ topic, question: q, session_id: conversation.sessionId, course_id: "default", language: "en" }),
    onSuccess: (reply) => push({ role: "tutor", reply }, reply.session_id),
    onError: (e) => push({ role: "error", text: (e as Error).message }),
  });
  const feedback = useMutation({ mutationFn: api.feedback });

  useEffect(() => {
    // a block body on purpose: in some browsers scrollIntoView returns a Promise, which must not be
    // returned to React as if it were a cleanup function
    endRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [conversation.messages.length]);

  function send(e: FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (!q || ask.isPending) return;
    push({ role: "student", text: q });
    setQuestion("");
    ask.mutate(q);
  }

  const lastTutor = [...conversation.messages].reverse().find((m) => m.role === "tutor") as
    | { role: "tutor"; reply: AskResponse }
    | undefined;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <TopicPicker value={topic} onChange={setTopic} />
        {lastTutor?.reply.kc_level && <Band band={lastTutor.reply.kc_level} label="Explained at level" />}
      </div>

      {profile.data && !profile.data.personalized && (
        <p className="rounded-md border border-sky-200 bg-sky-50 px-4 py-2 text-sm text-sky-900">
          Answers are not adapted to you yet. <Link to="/start" className="btn-link">Personalize your tutor</Link>
        </p>
      )}

      <section aria-label="Conversation" aria-live="polite" className="flex min-h-[40vh] flex-col gap-4">
        {conversation.messages.length === 0 && (
          <p className="text-slate-500">Ask anything about this topic, for example “What do the two numbers in a blood pressure reading mean?”</p>
        )}
        {conversation.messages.map((m, i) =>
          m.role === "student" ? (
            <div key={i} className="self-end max-w-[80%] rounded-lg bg-teal-700 px-4 py-2 text-white">{m.text}</div>
          ) : m.role === "error" ? (
            <p key={i} role="alert" className="text-sm text-rose-700">{m.text}</p>
          ) : (
            <TutorMessage key={i} reply={m.reply} sessionId={conversation.sessionId} />
          ),
        )}
        {ask.isPending && <p className="text-sm text-slate-500">The tutor is thinking…</p>}
        <div ref={endRef} />
      </section>

      <form onSubmit={send} className="sticky bottom-0 flex flex-col gap-2 border-t border-slate-200 bg-slate-50 pt-3">
        <label htmlFor="question" className="sr-only">Your question</label>
        <div className="flex gap-2">
          <textarea id="question" rows={2} className="input resize-y" placeholder="Type your question…" value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) send(e); }} />
          <button type="submit" className="btn-primary self-end" disabled={!question.trim() || ask.isPending}>Send</button>
        </div>
        {profile.data?.personalized && (
          <div className="flex flex-wrap items-center gap-2 text-sm" role="group" aria-label="How should answers look?">
            <span className="text-slate-600">Next answers:</span>
            {FEEDBACK.map((f) => (
              <button key={f.action} type="button" className="btn-secondary px-2.5 py-1 text-xs"
                      onClick={() => feedback.mutate(f.action)} disabled={feedback.isPending}>
                {f.label}
              </button>
            ))}
            {feedback.isSuccess && <span role="status" className="text-xs text-emerald-700">Saved.</span>}
          </div>
        )}
      </form>
    </div>
  );
}

function TutorMessage({ reply, sessionId }: { reply: AskResponse; sessionId: string }) {
  return (
    <article className="max-w-[90%] rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <p className="whitespace-pre-wrap text-slate-900">{reply.answer}</p>
      {!!reply.warnings?.length && (
        <ul className="mt-2 space-y-0.5 text-xs text-amber-800">
          {reply.warnings.map((w) => <li key={w}>⚠ {w}</li>)}
        </ul>
      )}
      {!!reply.sources?.length && (
        <div className="mt-3 text-xs text-slate-600">
          <span className="font-medium">Sources: </span>
          {reply.sources.map((s, i) => (
            <span key={s.source}>[{i + 1}] {s.title}{i < reply.sources!.length - 1 ? "; " : ""}</span>
          ))}
        </div>
      )}
      {reply.next_kc && (
        <p className="mt-2 text-xs text-slate-600">Suggested next: <strong>{reply.next_kc.name}</strong></p>
      )}
      {reply.check_item && <CheckCard item={reply.check_item} sessionId={sessionId} />}
    </article>
  );
}
