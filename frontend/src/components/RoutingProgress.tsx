import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import type { RoutingProgress as Progress } from "@/api/askStream";
import type { Schemas } from "@/api/client";
import { useI18n, type T } from "@/i18n";
import { en, type MessageKey } from "@/i18n/en";

export type RoutingTrace = {
  id: string; method: string; visible: boolean; events: Progress[]; running: boolean;
  startedAt: number; finishedAt?: number; details?: Schemas["RouteScore"] | null; error?: string;
};

const STAGES = ["preparation", "embedding", "classification", "retrieval", "evidence", "decision", "web_search",
  "generation", "verification"] as const;
// shown only when it ran: web search is off in most deployments and runs only for some cloud answers
const OPTIONAL_STAGES = new Set<string>(["web_search"]);
const STATUSES = ["pending", "running", "completed", "skipped", "failed"];

export function latestEvents(events: Progress[]): Progress[] {
  const byStage = new Map<string, Progress>();
  for (const event of events) byStage.set(event.stage, event);
  return [...byStage.values()];
}

const EVIDENCE_STATUSES = ["sufficient", "insufficient", "uncertain", "unavailable", "not_required", "empty"];

/** A plain-language line for a step. The backend sends English technical details; they are replaced by a
 *  translated sentence for the steps known here (a number is read from the detail). Anything else is shown as
 *  sent in English and hidden in another language, so a student never reads technical English in the French
 *  interface. */
function stepDetail(stage: string, status: string, detail: string, lang: string, t: T): string | null {
  const count = /(\d+)/.exec(detail)?.[1];
  const sentence = (key: string, vars?: Record<string, string | number>) => t(`routing.detail.${key}` as MessageKey, vars);
  let key: string | null = null;
  if (stage === "decision" && status === "completed") key = /^LOCAL/i.test(detail) ? "decision.completedLocal" : /^CLOUD/i.test(detail) ? "decision.completedCloud" : null;
  else if (status !== "running" && status !== "pending") key = `${stage}.${status}`;
  if (key && `routing.detail.${key}` in en && (count || !/\{n\}/.test(en[`routing.detail.${key}` as MessageKey]))) {
    if (count === "1" && `routing.detail.${key}One` in en) return sentence(`${key}One`);  // "1 passage", not "1 passages"
    return sentence(key, { n: count ?? 0 });
  }
  return lang === "en" ? detail : null;
}

/** The routing steps of one answer. Shown inside a collapsed panel; the content never includes question text. */
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
  return (
    <section aria-label={t("routing.region")} aria-live="off" className="w-full rounded-xl border bg-card px-4 py-3">
      <div className="mb-3 flex items-center justify-between gap-3 text-sm">
        <strong>{t("routing.title", { method: trace.method.toUpperCase() })}</strong>
        <span aria-hidden={trace.running || undefined} className="tabular-nums text-muted-foreground">{t(trace.running ? "routing.running" : trace.error ? "routing.failed" : "routing.finished")} · {(elapsed / 1000).toFixed(2)} s</span>
      </div>
      <ol className="relative space-y-2.5 before:absolute before:top-1.5 before:bottom-1.5 before:left-[5px] before:w-px before:bg-border">
        {STAGES.map((id) => {
          const e = events.find((p) => p.stage === id);
          if (!e && OPTIONAL_STAGES.has(id)) return null;
          const state = e?.status ?? "pending";
          const duration = e?.duration_ms ?? (state === "running" ? Math.max(0, elapsed - (e?.elapsed_ms ?? 0)) : null);
          return (
            <li key={id} className="relative pl-6 text-xs">
              <StageDot state={state} />
              <div className="flex items-center justify-between gap-3">
                <span className={state === "running" ? "font-semibold text-foreground" : state === "pending" ? "text-muted-foreground" : ""}>
                  {t(`routing.stage.${id}`)}{" "}
                  <span className="ml-1 text-muted-foreground">{STATUSES.includes(state) ? t(`routing.status.${state}` as MessageKey) : state}</span>
                </span>
                <span className="tabular-nums text-muted-foreground">{duration == null ? "—" : `${(duration / 1000).toFixed(3)} s`}</span>
              </div>
              {e?.detail && stepDetail(id, state, e.detail, lang, t) && <p className="mt-0.5 text-muted-foreground">{stepDetail(id, state, e.detail, lang, t)}</p>}
            </li>
          );
        })}
      </ol>
      {trace.details && (
        <div className="mt-3 border-t pt-2 text-xs">
          <strong>{t("routing.selected", { target: trace.details.target?.toUpperCase() ?? "" })}</strong>
          {trace.details.analysis && <span>{t("routing.cloudNeed", { p: ((trace.details.analysis.cloud_probability ?? 0) * 100).toFixed(1) })}</span>}
          {trace.details.evidence && <p>{t("routing.evidence", { status: EVIDENCE_STATUSES.includes(trace.details.evidence.status) ? t(`routing.evidenceStatus.${trace.details.evidence.status}` as MessageKey) : trace.details.evidence.status, p: ((trace.details.evidence.coverage ?? 0) * 100).toFixed(0) })}</p>}
          {trace.details.analysis?.label_origin === "prototype_policy" && <p className="mt-1 text-warning">{t("routing.prototype")}</p>}
        </div>
      )}
      {trace.error && <p className="mt-2 text-xs text-destructive">{trace.error}</p>}
    </section>
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
