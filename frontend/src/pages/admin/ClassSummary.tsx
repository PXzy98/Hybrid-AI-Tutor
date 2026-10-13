import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { admin, type ClassSummary } from "../../api/endpoints";
import TopicPicker from "../../components/TopicPicker";

const BANDS: { key: string; label: string; color: string }[] = [
  { key: "not_assessed", label: "Not assessed", color: "bg-slate-300" },
  { key: "basic", label: "Basic", color: "bg-amber-400" },
  { key: "intermediate", label: "Intermediate", color: "bg-sky-500" },
  { key: "advanced", label: "Advanced", color: "bg-teal-600" },
  { key: "mastered", label: "Mastered", color: "bg-emerald-700" },
];
const HIDDEN = "bg-[repeating-linear-gradient(45deg,#cbd5e1_0,#cbd5e1_4px,#f1f5f9_4px,#f1f5f9_8px)]";

/** One stacked bar per KC. Suppressed cells are pooled into one hatched "hidden" segment. */
function KcBar({ name, counts, total, min }: { name: string; counts: Record<string, number | null>; total: number; min: number }) {
  const shown = BANDS.filter((b) => (counts[b.key] ?? 0) > 0);
  const hidden = total - BANDS.reduce((s, b) => s + (counts[b.key] ?? 0), 0);
  const describe = BANDS.map((b) => `${b.label}: ${counts[b.key] === null ? `fewer than ${min}` : counts[b.key]}`).join(", ");
  return (
    <li className="space-y-1">
      <div className="text-sm">{name}</div>
      <div className="flex h-6 w-full overflow-hidden rounded bg-slate-100" role="img" aria-label={`${name}. ${describe}`}>
        {shown.map((b) => (
          <div key={b.key} className={`${b.color} flex items-center justify-center text-xs text-white`}
               style={{ width: `${(100 * (counts[b.key] ?? 0)) / total}%` }} title={`${b.label}: ${counts[b.key]}`}>
            {counts[b.key]}
          </div>
        ))}
        {hidden > 0 && (
          <div className={`${HIDDEN} flex items-center justify-center text-xs text-slate-700`}
               style={{ width: `${(100 * hidden) / total}%` }} title={`Groups smaller than ${min} are hidden`}>
            &lt;{min}
          </div>
        )}
      </div>
    </li>
  );
}

function Summary({ s }: { s: ClassSummary }) {
  if (s.suppressed) {
    return (
      <p className="card text-sm text-slate-700" role="status">
        Fewer than {s.min_group} students have a learning profile for this topic, so the summary is hidden to protect
        their privacy.
      </p>
    );
  }
  const total = s.students ?? 0;
  return (
    <div className="space-y-5">
      <section className="card space-y-4" aria-labelledby="kc-title">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="kc-title" className="font-semibold">Mastery by knowledge component</h2>
          <span className="text-sm text-slate-600">{total} students with a learning profile</span>
        </div>
        <ul className="flex flex-wrap gap-3 text-xs text-slate-700" aria-label="Legend">
          {BANDS.map((b) => (
            <li key={b.key} className="flex items-center gap-1"><span className={`inline-block h-3 w-3 rounded ${b.color}`} />{b.label}</li>
          ))}
          <li className="flex items-center gap-1"><span className={`inline-block h-3 w-3 rounded ${HIDDEN}`} />Hidden (groups &lt; {s.min_group})</li>
        </ul>
        <ul className="space-y-3">
          {s.kcs?.map((k) => <KcBar key={k.kc_id} name={k.name} counts={k.counts} total={total} min={s.min_group} />)}
        </ul>
      </section>
      <section className="card" aria-labelledby="mc-title">
        <h2 id="mc-title" className="mb-3 font-semibold">Most common misconceptions</h2>
        {s.misconceptions?.length ? (
          <ul className="space-y-2 text-sm">
            {s.misconceptions.map((m) => (
              <li key={m.misconception_id} className="flex items-start justify-between gap-3">
                <span>{m.statement}</span>
                <span className="whitespace-nowrap text-slate-600">{m.students} students</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-600">No misconception is held by {s.min_group} or more students.</p>
        )}
        {(s.misconceptions_hidden ?? 0) > 0 && (
          <p className="mt-3 text-xs text-slate-600">
            {s.misconceptions_hidden} more misconception(s) held by fewer than {s.min_group} students are not listed.
          </p>
        )}
      </section>
    </div>
  );
}

export default function ClassSummaryPage() {
  const [topic, setTopic] = useState("high_blood_pressure");
  const summary = useQuery({ queryKey: ["admin", "summary", topic], queryFn: () => admin.classSummary(topic) });
  return (
    <div className="space-y-4">
      <TopicPicker value={topic} onChange={setTopic} />
      {summary.isLoading && <p className="text-sm text-slate-600">Loading…</p>}
      {summary.isError && <p role="alert" className="text-sm text-rose-700">Could not load the class summary.</p>}
      {summary.data && <Summary s={summary.data} />}
    </div>
  );
}
