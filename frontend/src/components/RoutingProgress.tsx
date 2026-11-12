import { useEffect, useState } from "react";

import type { RoutingProgress as Progress } from "@/api/askStream";
import type { Schemas } from "@/api/client";
import { useI18n } from "@/i18n";
import type { MessageKey } from "@/i18n/en";

export type RoutingTrace = {
  id: string; method: string; visible: boolean; events: Progress[]; running: boolean;
  startedAt: number; finishedAt?: number; details?: Schemas["RouteScore"] | null; error?: string;
};

const STAGES = ["preparation", "embedding", "classification", "retrieval", "evidence", "decision",
  "generation", "verification"] as const;
const STATUSES = ["pending", "running", "completed", "skipped", "failed"];

export function latestEvents(events: Progress[]): Progress[] {
  const byStage = new Map<string, Progress>();
  for (const event of events) byStage.set(event.stage, event);
  return [...byStage.values()];
}

/** The routing steps of one answer. Shown inside a collapsed panel; the content never includes question text. */
export default function RoutingProgress({ trace }: { trace: RoutingTrace }) {
  const [now, setNow] = useState(Date.now());
  const { t } = useI18n();
  useEffect(() => {
    if (!trace.running) return;
    const timer = window.setInterval(() => setNow(Date.now()), 100);
    return () => window.clearInterval(timer);
  }, [trace.running]);
  const events = latestEvents(trace.events);
  const total = Math.max(0, (trace.finishedAt ?? now) - trace.startedAt);
  const eventEnd = Math.max(0, ...events.map((e) => e.elapsed_ms));
  const elapsed = trace.running ? Math.max(total, eventEnd) : eventEnd || total;
  return (
    <section aria-label={t("routing.region")} className="w-full rounded-lg border bg-muted/40 px-4 py-3">
      <div className="mb-3 flex items-center justify-between gap-3 text-sm">
        <strong>{t("routing.title", { method: trace.method.toUpperCase() })}</strong>
        <span className="tabular-nums text-muted-foreground">{t(trace.running ? "routing.running" : trace.error ? "routing.failed" : "routing.finished")} · {(elapsed / 1000).toFixed(2)} s</span>
      </div>
      <ol className="space-y-2">
        {STAGES.map((id) => {
          const e = events.find((p) => p.stage === id);
          const state = e?.status ?? "pending";
          const duration = e?.duration_ms ?? (state === "running" ? Math.max(0, elapsed - (e?.elapsed_ms ?? 0)) : null);
          return (
            <li key={id} className="text-xs">
              <div className="flex items-center justify-between gap-3">
                <span className={state === "running" ? "font-semibold text-primary" : ""}>
                  {t(`routing.stage.${id}`)}{" "}
                  <span className="ml-1 text-muted-foreground">{STATUSES.includes(state) ? t(`routing.status.${state}` as MessageKey) : state}</span>
                </span>
                <span className="tabular-nums text-muted-foreground">{duration == null ? "—" : `${(duration / 1000).toFixed(3)} s`}</span>
              </div>
              {e?.detail && <p className="mt-0.5 text-muted-foreground">{e.detail}</p>}
            </li>
          );
        })}
      </ol>
      {trace.details && (
        <div className="mt-3 border-t pt-2 text-xs">
          <strong>{t("routing.selected", { target: trace.details.target?.toUpperCase() ?? "" })}</strong>
          {trace.details.analysis && <span>{t("routing.cloudNeed", { p: (trace.details.analysis.cloud_probability * 100).toFixed(1) })}</span>}
          {trace.details.evidence && <p>{t("routing.evidence", { status: trace.details.evidence.status, p: (trace.details.evidence.coverage * 100).toFixed(0) })}</p>}
          {trace.details.analysis?.label_origin === "prototype_policy" && <p className="mt-1 text-amber-700 dark:text-amber-300">{t("routing.prototype")}</p>}
        </div>
      )}
      {trace.error && <p className="mt-2 text-xs text-destructive">{trace.error}</p>}
    </section>
  );
}
