import { ArrowDown, RotateCw } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";

import type { AskResponse } from "@/api/endpoints";
import { ErrorNote, Loading } from "@/components/common";
import Markdown from "@/components/LazyMarkdown";
import type { RoutingTrace } from "@/components/RoutingProgress";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n";
import EmptyChat from "./EmptyChat";
import RoutingPanel from "./RoutingPanel";
import TutorMessage, { answerBody, CopyAnswer, TutorFrame } from "./TutorMessage";

export type Message =
  | { role: "student"; text: string }
  | { role: "tutor"; reply: AskResponse }
  | { role: "history"; text: string }
  | { role: "error"; error: unknown; question?: string }
  | { role: "routing"; trace: RoutingTrace };

const NEAR_BOTTOM = 80;  // px: closer than this to the end counts as "reading the latest"

type Props = {
  courseId: number;
  messages: Message[];
  partial: string;
  pending: boolean;
  loadingHistory: boolean;
  historyError: unknown;
  onSuggest: (text: string) => void;
  onRetry: (question: string) => void;
  children: ReactNode;  // the composer
};

/** The conversation and, pinned under it, the composer. Follows new text only while the reader is at the end. */
export default function MessageList({ courseId, messages, partial, pending, loadingHistory, historyError, onSuggest, onRetry, children }: Props) {
  const { t } = useI18n();
  const endRef = useRef<HTMLDivElement>(null);
  const atEnd = useRef(true);
  const [away, setAway] = useState(false);
  // only sending adds a routing entry (stored history has none), so their count tells a new question apart
  const sentCount = messages.filter((m) => m.role === "routing").length;
  const lastSentCount = useRef(sentCount);

  // the app's content area (main) is the scrolling element
  useEffect(() => {
    const scroller = endRef.current?.closest("main");
    if (!scroller) return;
    const onScroll = () => {
      atEnd.current = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight <= NEAR_BOTTOM;
      setAway(!atEnd.current);
    };
    scroller.addEventListener("scroll", onScroll, { passive: true });
    return () => scroller.removeEventListener("scroll", onScroll);
  }, []);

  useLayoutEffect(() => {
    // a question the student just sent always brings the end into view; new tutor text only if they are there
    const sent = sentCount > lastSentCount.current;
    lastSentCount.current = sentCount;
    if (!sent && !atEnd.current) return;
    // a block body on purpose: in some browsers scrollIntoView returns a Promise, which must not be
    // returned to React as if it were a cleanup function
    endRef.current?.scrollIntoView?.({ block: "end" });
  }, [messages.length, partial, sentCount]);

  function jump() {
    atEnd.current = true;
    setAway(false);
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    endRef.current?.scrollIntoView?.({ behavior: reduced ? "auto" : "smooth", block: "end" });
  }

  // one polite announcement when an answer is complete; the conversation itself is not a live region
  const [announcement, setAnnouncement] = useState("");
  const announced = useRef<unknown>(null);
  const last = messages[messages.length - 1];
  useEffect(() => {
    if (pending) setAnnouncement("");
    else if (last?.role === "tutor" && last.reply !== announced.current) {
      announced.current = last.reply;  // an error is announced by its own role=alert note
      setAnnouncement(t("chat.answerReady"));
    }
  }, [pending, last, t]);

  const empty = messages.length === 0 && !loadingHistory;

  return (
    <div className="flex flex-col">
      <section aria-label={t("chat.conversation")} className="flex flex-col gap-6 pb-6">
        <div role="status" aria-live="polite" className="sr-only">{announcement}</div>
        {loadingHistory && <Loading variant="chat" />}
        <ErrorNote error={historyError} />
        {empty && <EmptyChat onSuggest={onSuggest} />}
        {messages.map((m, i) =>
          m.role === "student" ? (
            <div key={i} className="animate-in-up max-w-[85%] self-end rounded-2xl bg-secondary px-4 py-2.5 text-[0.9375rem] leading-7 whitespace-pre-wrap">{m.text}</div>
          ) : m.role === "routing" ? (
            m.trace.visible ? <RoutingPanel key={m.trace.id} trace={m.trace} /> : null
          ) : m.role === "error" ? (
            <div key={i} className="space-y-2">
              <ErrorNote error={m.error} />
              {m.question && i === messages.length - 1 && !pending && (
                <Button type="button" variant="outline" size="sm" onClick={() => onRetry(m.question as string)}>
                  <RotateCw aria-hidden />{t("app.retry")}
                </Button>
              )}
            </div>
          ) : m.role === "history" ? (
            <TutorFrame key={i}>
              <div className={answerBody}><Markdown>{m.text}</Markdown></div>
              <CopyAnswer text={m.text} />
            </TutorFrame>
          ) : (
            <TutorMessage key={i} reply={m.reply} courseId={courseId} />
          ),
        )}
        {pending && partial && (
          <TutorFrame>
            <div className={`${answerBody} streaming`}><Markdown>{partial}</Markdown></div>
          </TutorFrame>
        )}
        {pending && !partial && (
          <TutorFrame>
            <div role="status" className="flex h-7 items-center gap-1" >
              <span className="sr-only">{t("chat.thinking")}</span>
              {[0, 1, 2].map((d) => (
                <span key={d} aria-hidden className="animate-shimmer size-1.5 rounded-full bg-muted-foreground"
                      style={{ animationDelay: `${d * 160}ms` }} />
              ))}
            </div>
          </TutorFrame>
        )}
      </section>

      <div className="sticky bottom-0 z-10 -mx-1 bg-background px-1 pt-1 pb-2">
        {away && !empty && (
          <div className="pointer-events-none absolute inset-x-0 -top-12 flex justify-center">
            <Button type="button" variant="outline" size="icon" className="pointer-events-auto rounded-full shadow-float"
                    aria-label={t("chat.jump")} onClick={jump}>
              <ArrowDown aria-hidden />
            </Button>
          </div>
        )}
        {children}
      </div>
      {/* below the sticky composer: scrolling this into view shows the whole conversation, none of it under the composer */}
      <div ref={endRef} />
    </div>
  );
}
