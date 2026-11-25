import { ChevronRight, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import type { RoutingProgress as Progress } from "@/api/askStream";
import type { Schemas } from "@/api/client";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useI18n, type T } from "@/i18n";
import { en, type MessageKey } from "@/i18n/en";
import { fr } from "@/i18n/fr";

export type RoutingTrace = {
  id: string; method: string; visible: boolean; events: Progress[]; running: boolean;
  startedAt: number; finishedAt?: number; details?: Schemas["RouteScore"] | null; error?: string;
  /** the router chose the cloud model but a privacy check kept the question on the local model */
  privacyKeptLocal?: boolean;
  /** the model that actually answered (the response's route_target): differs from the routing decision when the
   *  cloud model was missing, failed or reached its limit and the local model answered instead */
  answeredBy?: "local" | "cloud";
};

const STAGES = ["preparation", "embedding", "classification", "retrieval", "evidence", "decision", "web_search",
  "generation", "verification"] as const;
// shown only when it ran: web search is off in most deployments and runs only for some cloud answers
const OPTIONAL_STAGES = new Set<string>(["web_search"]);
const STATUSES = ["pending", "running", "completed", "skipped", "failed"];

// the notice the backend adds to the answer when a privacy check overrides the cloud route, in the language of
// the request: the only signal of the override in the answer
const PRIVACY_KEPT_LOCAL_NOTICES = [en["routing.privacyNotice"], fr["routing.privacyNotice"]];

export function keptLocalByPrivacy(details: Schemas["RouteScore"] | null | undefined, warnings: string[] | undefined): boolean {
  return details?.target === "cloud" && !!warnings?.some((w) => PRIVACY_KEPT_LOCAL_NOTICES.includes(w));
}

/** The plain summary under the steps, from the model that answered, not only from the routing decision. It says the
 *  question stayed on the course server only when nothing was sent out: the decision was local and no web search
 *  ran. It gives no single reason for a cloud answer, since the router weighs several. */
export function summaryKey(trace: RoutingTrace, events: Progress[]): MessageKey | null {
  const decided = trace.details?.target;
  const answered = trace.answeredBy ?? decided;
  if (answered === "cloud") return "routing.summaryCloud";
  if (answered !== "local") return null;
  const searched = events.some((e) => e.stage === "web_search" && e.status === "completed");
  return decided === "local" && !searched ? "routing.summaryLocal" : "routing.summaryLocalAnswered";
}

export function latestEvents(events: Progress[]): Progress[] {
  const byStage = new Map<string, Progress>();
  for (const event of events) byStage.set(event.stage, event);
  return [...byStage.values()];
}

const EVIDENCE_STATUSES = ["sufficient", "insufficient", "uncertain", "unavailable", "not_required", "empty"];

/** A plain-language line for a step. The backend sends English technical details; they are replaced by a
 *  translated sentence for the steps known here (a number is read from the detail). Anything else is shown as
 *  sent in English and hidden in another language, so a student never reads technical English in the French
 *  interface. `plainOnly` (the default student view) never shows the raw backend text. */
function stepDetail(stage: string, status: string, detail: string, lang: string, t: T, plainOnly = false): string | null {
  const count = /(\d+)/.exec(detail)?.[1];
  const sentence = (key: string, vars?: Record<string, string | number>) => t(`routing.detail.${key}` as MessageKey, vars);
  let key: string | null = null;
  if (stage === "decision" && status === "completed") key = /^LOCAL/i.test(detail) ? "decision.completedLocal" : /^CLOUD/i.test(detail) ? "decision.completedCloud" : null;
  else if (status !== "running" && status !== "pending") key = `${stage}.${status}`;
  if (key && `routing.detail.${key}` in en && (count || !/\{n\}/.test(en[`routing.detail.${key}` as MessageKey]))) {
    if (count === "1" && `routing.detail.${key}One` in en) return sentence(`${key}One`);  // "1 passage", not "1 passages"
    return sentence(key, { n: count ?? 0 });
  }
  return lang === "en" && !plainOnly ? detail : null;
}

/** The routing steps of one answer. Shown inside a collapsed panel; the content never includes question text.
 *  The default view is plain language; the technical values sit in a collapsed "Details" section. */
export default function RoutingProgress({ trace }: { trace: RoutingTrace }) {
  const [now, setNow] = useState(Date.now());
  const { t, lang } = useI18n();
  useEffect(() => {
    if (!trace.running) return;
    const timer = window.setInterval(() => setNow(Date.now()), 200);
    return () => window.clearInterval(timer);
  }, [trace.running]);
  const events = latestEvents(trace.events);
  const total = Math.max(0, (trace.finishedAt ?? now) - trace.startedAt);
  const eventEnd = Math.max(0, ...events.map((e) => e.elapsed_ms));
  const elapsed = trace.running ? Math.max(total, eventEnd) : eventEnd || total;
  const summary = summaryKey(trace, events);
  const shown = STAGES.filter((id) => events.some((p) => p.stage === id) || !OPTIONAL_STAGES.has(id));
  return (
    <section aria-label={t("routing.region")} aria-live="off" className="w-full rounded-xl border bg-card px-4 py-3">
      <ol className="relative space-y-2.5 before:absolute before:top-1.5 before:bottom-1.5 before:left-[5px] before:w-px before:bg-border">
        {shown.map((id) => {
          const e = events.find((p) => p.stage === id);
          const state = e?.status ?? "pending";
          const sentence = e?.detail ? stepDetail(id, state, e.detail, lang, t, true) : null;
          return (
            <li key={id} className="relative pl-6 text-xs">
              <StageDot state={state} />
              <span className={state === "running" ? "font-semibold text-foreground" : state === "pending" ? "text-muted-foreground" : ""}>
                {t(`routing.plain.${id}` as MessageKey)}
              </span>
              {sentence && <p className="mt-0.5 text-muted-foreground">{sentence}</p>}
            </li>
          );
        })}
        {trace.privacyKeptLocal && !trace.running && (
          <li className="relative pl-6 text-xs">
            <StageDot state="completed" />
            {t("routing.privacyKeptLocal")}
          </li>
        )}
      </ol>
      {!trace.running && !trace.error && summary && !trace.privacyKeptLocal && (
        <p className="mt-3 border-t pt-2 text-xs">{t(summary)}</p>
      )}
      {trace.error && <p className="mt-2 text-xs text-destructive">{trace.error}</p>}
      <Collapsible className="mt-3 border-t pt-2">
        <CollapsibleTrigger className="group inline-flex items-center gap-1 rounded text-xs text-muted-foreground outline-hidden hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring">
          <ChevronRight aria-hidden className="size-3.5 transition-transform group-data-[state=open]:rotate-90 motion-reduce:transition-none" />
          {t("routing.details")}
        </CollapsibleTrigger>
        <CollapsibleContent>
          <TechnicalDetails trace={trace} events={events} elapsed={elapsed} lang={lang} />
        </CollapsibleContent>
      </Collapsible>
    </section>
  );
}

/** The values shown at Design Day: method, status words, timings and the raw routing scores. */
function TechnicalDetails({ trace, events, elapsed, lang }: { trace: RoutingTrace; events: Progress[]; elapsed: number; lang: string }) {
  const { t } = useI18n();
  const d = trace.details;
  const target = d?.target;
  return (
    <div className="mt-2 space-y-2 text-xs">
      <div className="flex items-center justify-between gap-3">
        <strong>{t("routing.title", { method: trace.method.toUpperCase() })}</strong>
        <span className="tabular-nums text-muted-foreground">{t(trace.running ? "routing.running" : trace.error ? "routing.failed" : "routing.finished")} · {(elapsed / 1000).toFixed(2)} s</span>
      </div>
      <ul className="space-y-1">
        {STAGES.map((id) => {
          const e = events.find((p) => p.stage === id);
          if (!e && OPTIONAL_STAGES.has(id)) return null;
          const state = e?.status ?? "pending";
          const duration = e?.duration_ms ?? (state === "running" ? Math.max(0, elapsed - (e?.elapsed_ms ?? 0)) : null);
          const raw = e?.detail ? stepDetail(id, state, e.detail, lang, t) : null;
          return (
            <li key={id}>
              <div className="flex items-center justify-between gap-3">
                <span>{t(`routing.stage.${id}`)} <span className="ml-1 text-muted-foreground">{STATUSES.includes(state) ? t(`routing.status.${state}` as MessageKey) : state}</span></span>
                {duration != null && duration >= 0.5 && <span className="tabular-nums text-muted-foreground">{(duration / 1000).toFixed(3)} s</span>}
              </div>
              {raw && <p className="text-muted-foreground">{raw}</p>}
            </li>
          );
        })}
      </ul>
      {d && (
        <div className="border-t pt-2">
          {target && <strong>{t("routing.selected", { target: t(target === "local" ? "chat.local" : "chat.cloud") })}</strong>}
          {d.analysis && <span>{t("routing.cloudNeed", { p: ((d.analysis.cloud_probability ?? 0) * 100).toFixed(1) })}</span>}
          {d.evidence && <p>{t("routing.evidence", { status: EVIDENCE_STATUSES.includes(d.evidence.status) ? t(`routing.evidenceStatus.${d.evidence.status}` as MessageKey) : d.evidence.status, p: ((d.evidence.coverage ?? 0) * 100).toFixed(0) })}</p>}
          {d.analysis?.label_origin === "prototype_policy" && <p className="mt-1 text-warning">{t("routing.prototype")}</p>}
        </div>
      )}
    </div>
  );
}

/** The timeline dot of a stage. The status word next to it carries the meaning; the dot only repeats it. */
function StageDot({ state }: { state: string }) {
  const base = "absolute top-0.5 left-0 flex size-[11px] items-center justify-center rounded-full";
  if (state === "running") return <Loader2 aria-hidden className={`${base} animate-spin motion-reduce:animate-none bg-card text-primary`} />;
  if (state === "completed") return <span aria-hidden className={`${base} bg-primary`} />;
  if (state === "failed") return <span aria-hidden className={`${base} bg-destructive`} />;
  if (state === "skipped") return <span aria-hidden className={`${base} bg-card`}><span className="h-px w-1.5 bg-muted-foreground" /></span>;
  return <span aria-hidden className={`${base} border border-input bg-card`} />;
}
