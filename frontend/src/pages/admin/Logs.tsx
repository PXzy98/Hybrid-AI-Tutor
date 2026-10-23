import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { admin } from "../../api/endpoints";
import { useI18n } from "../../i18n";

const PAGE_SIZE = 20;

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="card py-3">
      <div className="text-xs text-slate-600">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}

const ms = (v?: number | null) => (v == null ? "–" : v >= 1000 ? `${(v / 1000).toFixed(1)} s` : `${Math.round(v)} ms`);

/** Sanitized request logs (no student or session IDs), latency and the local/cloud share.
 * The route is the router's decision; when a cloud call fails, the local model answers (see "answered by"). */
export default function LogsPage() {
  const [page, setPage] = useState(1);
  const { t, locale } = useI18n();
  const logs = useQuery({ queryKey: ["admin", "logs", page], queryFn: () => admin.logs(page, PAGE_SIZE),
                          placeholderData: keepPreviousData });
  if (logs.isLoading) return <p className="text-sm text-slate-600">{t("app.loading")}</p>;
  if (logs.isError || !logs.data) return <p role="alert" className="text-sm text-rose-700">{t("logs.loadError")}</p>;
  const { stats, entries, total } = logs.data;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label={t("logs.questions")} value={String(stats.requests)} />
        <Stat label={t("logs.cloudShare")} value={stats.cloud_share == null ? "–" : `${Math.round(stats.cloud_share * 100)}%`} />
        <Stat label={t("logs.p50")} value={ms(stats.latency_p50_ms)} />
        <Stat label={t("logs.p95")} value={ms(stats.latency_p95_ms)} />
      </div>
      <section className="card overflow-x-auto" aria-label={t("logs.requests")}>
        {entries.length === 0 ? (
          <p className="text-sm text-slate-600">{t("logs.none")}</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="text-slate-600">
              <tr>
                <th className="py-2 pr-3 font-medium">{t("logs.col.time")}</th>
                <th className="py-2 pr-3 font-medium">{t("logs.col.question")}</th>
                <th className="py-2 pr-3 font-medium">{t("logs.col.route")}</th>
                <th className="py-2 pr-3 font-medium">{t("logs.col.latency")}</th>
                <th className="py-2 font-medium">{t("logs.col.checks")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 align-top">
              {entries.map((e) => (
                <tr key={e.request_id}>
                  <td className="whitespace-nowrap py-2 pr-3">{new Date(e.created_at).toLocaleString(locale)}</td>
                  <td className="py-2 pr-3">{e.sanitized_question}</td>
                  <td className="py-2 pr-3">
                    {e.target ?? "–"}{e.route_score != null && <span className="text-xs text-slate-500"> ({e.route_score.toFixed(2)})</span>}
                    {e.model && <div className="text-xs text-slate-500">{t("logs.answeredBy", { model: e.model })}</div>}
                  </td>
                  <td className="whitespace-nowrap py-2 pr-3">{ms(e.latency_ms)}</td>
                  <td className="py-2 text-xs">
                    {Object.entries(e.checks).map(([name, st]) => (
                      <span key={name} className={`mr-1 inline-block rounded px-1 ${st === "pass" ? "bg-emerald-50 text-emerald-800" : st === "warn" ? "bg-amber-50 text-amber-900" : "bg-rose-50 text-rose-800"}`}>
                        {name}: {st}
                      </span>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      <div className="flex items-center gap-3 text-sm">
        <button type="button" className="btn-secondary py-1" disabled={page <= 1} onClick={() => setPage(page - 1)}>{t("logs.previous")}</button>
        <span>{t("logs.page", { page, pages })}</span>
        <button type="button" className="btn-secondary py-1" disabled={page >= pages} onClick={() => setPage(page + 1)}>{t("logs.next")}</button>
      </div>
    </div>
  );
}
