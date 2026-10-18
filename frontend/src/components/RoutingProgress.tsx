import { useEffect, useState } from "react";
import type { RoutingProgress as Progress } from "../api/askStream";
import type { Schemas } from "../api/client";

export type RoutingTrace = {
  id: string; method: string; visible: boolean; events: Progress[]; running: boolean;
  startedAt: number; finishedAt?: number; details?: Schemas["RouteScore"] | null; error?: string;
};

const STAGES = [
  ["preparation", "Prepare course context"], ["embedding", "Semantic encoding"],
  ["classification", "Capability and evidence classification"], ["retrieval", "Course material retrieval"],
  ["evidence", "Evidence validation"], ["decision", "Local / Cloud decision"],
  ["generation", "Generate answer"], ["verification", "Check answer"],
] as const;

export function latestEvents(events: Progress[]): Progress[] {
  const byStage = new Map<string, Progress>();
  for (const event of events) byStage.set(event.stage, event);
  return [...byStage.values()];
}

export default function RoutingProgress({ trace }: { trace: RoutingTrace }) {
  const [now, setNow] = useState(Date.now());
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
    <section aria-label="Routing progress" className="w-full max-w-2xl rounded-lg border border-teal-200 bg-teal-50/60 px-4 py-3">
      <div className="mb-3 flex items-center justify-between gap-3 text-sm">
        <strong>Routing · {trace.method.toUpperCase()}</strong>
        <span className="tabular-nums text-slate-600">{trace.running ? "Running" : trace.error ? "Failed" : "Finished"} · {(elapsed / 1000).toFixed(2)} s</span>
      </div>
      <ol className="space-y-2">
        {STAGES.map(([id, label]) => {
          const e = events.find((p) => p.stage === id);
          const state = e?.status ?? "pending";
          const duration = e?.duration_ms ?? (state === "running" ? Math.max(0, elapsed - (e?.elapsed_ms ?? 0)) : null);
          return (
            <li key={id} className="text-xs">
              <div className="flex items-center justify-between gap-3">
                <span className={state === "running" ? "font-semibold text-teal-800" : "text-slate-700"}>
                  {label} <span className="ml-1 text-slate-500">{state}</span>
                </span>
                <span className="tabular-nums text-slate-600">{duration == null ? "—" : `${(duration / 1000).toFixed(3)} s`}</span>
              </div>
              {e?.detail && <p className="mt-0.5 text-slate-500">{e.detail}</p>}
            </li>
          );
        })}
      </ol>
      {trace.details && (
        <div className="mt-3 border-t border-teal-200 pt-2 text-xs text-slate-700">
          <strong>Selected: {trace.details.target?.toUpperCase()}</strong>
          {trace.details.analysis && <span> · Estimated Cloud need: {(trace.details.analysis.cloud_probability * 100).toFixed(1)}%</span>}
          {trace.details.evidence && <p>Evidence: {trace.details.evidence.status} · Support coverage: {(trace.details.evidence.coverage * 100).toFixed(0)}%</p>}
          {trace.details.analysis?.label_origin === "prototype_policy" && <p className="mt-1 text-amber-800">Prototype policy labels; capability estimates still need benchmarking.</p>}
        </div>
      )}
      {trace.error && <p className="mt-2 text-xs text-rose-700">{trace.error}</p>}
    </section>
  );
}
