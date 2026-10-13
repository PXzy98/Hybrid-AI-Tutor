import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";

import { admin, type RuntimeConfig } from "../../api/endpoints";

const CHECKER_LABELS: Record<string, string> = {
  grounding: "Grounding (answer supported by the course material)",
  medical_safety: "Medical safety",
  pii_leak: "Personal data leak",
  profile_leak: "Learner-profile leak",
};

function NumberField({ id, label, value, onChange, step = 0.05, hint }: {
  id: string; label: string; value: number; onChange: (v: number) => void; step?: number; hint?: string;
}) {
  return (
    <div>
      <label className="label" htmlFor={id}>{label}</label>
      <input id={id} type="number" className="input max-w-32" min={0} max={1} step={step} value={value}
             onChange={(e) => onChange(Number(e.target.value))} aria-describedby={hint ? `${id}-hint` : undefined} />
      {hint && <p id={`${id}-hint`} className="mt-1 text-xs text-slate-600">{hint}</p>}
    </div>
  );
}

/** Runtime settings: applied at once (the next question uses them) and kept in the change history. */
export default function SettingsPage() {
  const qc = useQueryClient();
  const cfg = useQuery({ queryKey: ["admin", "config"], queryFn: admin.config });
  const [v, setV] = useState<RuntimeConfig | null>(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    if (cfg.data) setV(cfg.data.values);
  }, [cfg.data]);
  const save = useMutation({
    mutationFn: (values: RuntimeConfig) => admin.saveConfig(values),
    onSuccess: (data) => {
      qc.setQueryData(["admin", "config"], data);
      setSaved(true);
    },
  });

  if (cfg.isLoading || !v) return <p className="text-sm text-slate-600">Loading…</p>;
  if (cfg.isError || !cfg.data) return <p role="alert" className="text-sm text-rose-700">Could not load the settings.</p>;
  const { options, history } = cfg.data;
  const set = (patch: Partial<RuntimeConfig>) => {
    setSaved(false);
    setV({ ...v, ...patch });
  };
  const setLevel = (key: keyof RuntimeConfig["levels"], value: number) => set({ levels: { ...v.levels, [key]: value } });
  const toggleChecker = (name: string) =>
    set({ checkers: v.checkers.includes(name) ? v.checkers.filter((c) => c !== name) : [...v.checkers, name] });

  function submit(e: FormEvent) {
    e.preventDefault();
    save.mutate(v!);
  }

  return (
    <div className="space-y-5">
      <form onSubmit={submit} className="card space-y-5">
        <fieldset className="space-y-2">
          <legend className="font-semibold">Routing</legend>
          <NumberField id="threshold" label="Cloud threshold" value={v.routing_threshold}
                       onChange={(x) => set({ routing_threshold: x })}
                       hint="A question goes to the cloud model when its route score is at or above this value. Questions with sensitive personal data always stay local." />
        </fieldset>

        <fieldset className="space-y-2">
          <legend className="font-semibold">Answer checks</legend>
          {options.checkers.map((name) => {
            const required = options.required_checkers.includes(name);
            return (
              <label key={name} className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={v.checkers.includes(name)} disabled={required}
                       onChange={() => toggleChecker(name)} />
                {CHECKER_LABELS[name] ?? name}
                {required && <span className="text-xs text-slate-500">(always on)</span>}
              </label>
            );
          })}
        </fieldset>

        <fieldset className="space-y-3">
          <legend className="font-semibold">Learner model</legend>
          <div>
            <label className="label" htmlFor="knowledge">Knowledge model</label>
            <select id="knowledge" className="input max-w-56" value={v.knowledge} onChange={(e) => set({ knowledge: e.target.value })}>
              {options.knowledge_models.map((k) => <option key={k} value={k}>{k === "bkt" ? "BKT (Bayesian)" : k === "rule" ? "Rule (recent answers)" : k}</option>)}
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={v.weak_evidence} onChange={(e) => set({ weak_evidence: e.target.checked })} />
            Use weak evidence from questions (confusion, stated misconceptions) in the mastery estimate
          </label>
          <div className="flex flex-wrap gap-4">
            <NumberField id="basic-below" label="Basic below" value={v.levels.basic_below}
                         onChange={(x) => setLevel("basic_below", x)} />
            <NumberField id="advanced-above" label="Advanced above" value={v.levels.advanced_above}
                         onChange={(x) => setLevel("advanced_above", x)} />
            <NumberField id="hysteresis" label="Hysteresis" value={v.levels.hysteresis} step={0.01}
                         onChange={(x) => setLevel("hysteresis", x)} />
          </div>
        </fieldset>

        <div className="flex items-center gap-3">
          <button type="submit" className="btn-primary" disabled={save.isPending}>Save and apply</button>
          {saved && <span role="status" className="text-sm text-teal-800">Saved. The next question uses the new settings.</span>}
          {save.isError && <span role="alert" className="text-sm text-rose-700">{(save.error as Error).message}</span>}
        </div>
      </form>

      <section className="card" aria-labelledby="hist-title">
        <h2 id="hist-title" className="mb-2 font-semibold">Change history</h2>
        {history.length === 0 ? (
          <p className="text-sm text-slate-600">No changes yet: the values come from config.yaml.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {history.map((h) => (
              <li key={h.changed_at}>{new Date(h.changed_at).toLocaleString()}: {h.changed.join(", ")}</li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
