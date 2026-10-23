import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";

import { admin, type RuntimeConfig, type ServerStatus } from "../../api/endpoints";
import { useI18n } from "../../i18n";
import type { MessageKey } from "../../i18n/en";

const KNOWN_CHECKERS = ["grounding", "medical_safety", "pii_leak", "profile_leak"];

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
  const { t, locale } = useI18n();
  const cfg = useQuery({ queryKey: ["admin", "config"], queryFn: admin.config });
  const [v, setV] = useState<RuntimeConfig | null>(null);
  const [saved, setSaved] = useState(false);
  const [server, setServer] = useState<ServerStatus | null>(null);
  useEffect(() => {
    if (cfg.data) setV(cfg.data.values);
  }, [cfg.data]);
  const test = useMutation({
    mutationFn: ({ url, model }: { url: string; model: string }) => admin.testLlmServer(url, model),
    onSuccess: setServer,
  });
  const save = useMutation({
    mutationFn: (values: RuntimeConfig) => admin.saveConfig(values),
    onSuccess: (data) => {
      qc.setQueryData(["admin", "config"], data);
      setSaved(true);
    },
  });

  if (cfg.isError) return <p role="alert" className="text-sm text-rose-700">{t("settings.loadError")}</p>;
  if (cfg.isLoading || !v || !cfg.data) return <p className="text-sm text-slate-600">{t("app.loading")}</p>;
  const { options, history } = cfg.data;
  const set = (patch: Partial<RuntimeConfig>) => {
    setSaved(false);
    if ("local_llm_url" in patch || "local_llm_model" in patch) setServer(null);
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
          <legend className="font-semibold">{t("settings.routing")}</legend>
          <NumberField id="threshold" label={t("settings.threshold")} value={v.routing_threshold}
                       onChange={(x) => set({ routing_threshold: x })}
                       hint={t("settings.thresholdHint")} />
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={v.show_routing_progress ?? true}
                   onChange={(e) => set({ show_routing_progress: e.target.checked })} />
            {t("settings.showProgress")}
          </label>
          <p className="text-xs text-slate-600">{t("settings.showProgressHint")}</p>
        </fieldset>

        <fieldset className="space-y-3">
          <legend className="font-semibold">{t("settings.server")}</legend>
          <p className="text-xs text-slate-600">
            {t("settings.serverHint")}
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="label" htmlFor="llm-url">{t("settings.serverUrl")}</label>
              <input id="llm-url" className="input w-72" placeholder="http://10.0.0.5:11434"
                     value={v.local_llm_url ?? ""} onChange={(e) => set({ local_llm_url: e.target.value })} />
            </div>
            <div>
              <label className="label" htmlFor="llm-model">{t("settings.serverModel")}</label>
              <input id="llm-model" className="input w-48" placeholder="qwen3.5:9b"
                     value={v.local_llm_model ?? ""} onChange={(e) => set({ local_llm_model: e.target.value })} />
            </div>
            <button type="button" className="btn-secondary" disabled={test.isPending || !v.local_llm_url || !v.local_llm_model}
                    onClick={() => test.mutate({ url: v.local_llm_url ?? "", model: v.local_llm_model ?? "" })}>
              {test.isPending ? t("settings.testing") : t("settings.test")}
            </button>
          </div>
          {server && (
            <p role="status" className={`text-sm ${server.reachable && server.model_available ? "text-teal-800" : "text-rose-700"}`}>
              {server.reachable && server.model_available
                ? t("settings.connected", { ms: server.latency_ms ?? "–" })
                : server.error}
              {server.reachable && !server.model_available && server.models.length > 0 &&
                t("settings.serverModels", { models: server.models.join(", ") })}
            </p>
          )}
          {test.isError && <p role="alert" className="text-sm text-rose-700">{(test.error as Error).message}</p>}
        </fieldset>

        <fieldset className="space-y-2">
          <legend className="font-semibold">{t("settings.checks")}</legend>
          {options.checkers.map((name) => {
            const required = options.required_checkers.includes(name);
            return (
              <label key={name} className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={v.checkers.includes(name)} disabled={required}
                       onChange={() => toggleChecker(name)} />
                {KNOWN_CHECKERS.includes(name) ? t(`settings.checker.${name}` as MessageKey) : name}
                {required && <span className="text-xs text-slate-500">{t("settings.alwaysOn")}</span>}
              </label>
            );
          })}
        </fieldset>

        <fieldset className="space-y-3">
          <legend className="font-semibold">{t("settings.learner")}</legend>
          <div>
            <label className="label" htmlFor="knowledge">{t("settings.knowledge")}</label>
            <select id="knowledge" className="input max-w-56" value={v.knowledge} onChange={(e) => set({ knowledge: e.target.value })}>
              {options.knowledge_models.map((k) => <option key={k} value={k}>{k === "bkt" || k === "rule" ? t(`settings.knowledge.${k}`) : k}</option>)}
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={v.weak_evidence} onChange={(e) => set({ weak_evidence: e.target.checked })} />
            {t("settings.weak")}
          </label>
          <div className="flex flex-wrap gap-4">
            <NumberField id="basic-below" label={t("settings.basicBelow")} value={v.levels.basic_below}
                         onChange={(x) => setLevel("basic_below", x)} />
            <NumberField id="advanced-above" label={t("settings.advancedAbove")} value={v.levels.advanced_above}
                         onChange={(x) => setLevel("advanced_above", x)} />
            <NumberField id="hysteresis" label={t("settings.hysteresis")} value={v.levels.hysteresis} step={0.01}
                         onChange={(x) => setLevel("hysteresis", x)} />
          </div>
        </fieldset>

        <div className="flex items-center gap-3">
          <button type="submit" className="btn-primary" disabled={save.isPending}>{t("settings.save")}</button>
          {saved && <span role="status" className="text-sm text-teal-800">{t("settings.saved")}</span>}
          {save.isError && <span role="alert" className="text-sm text-rose-700">{(save.error as Error).message}</span>}
        </div>
      </form>

      <section className="card" aria-labelledby="hist-title">
        <h2 id="hist-title" className="mb-2 font-semibold">{t("settings.history")}</h2>
        {history.length === 0 ? (
          <p className="text-sm text-slate-600">{t("settings.noHistory")}</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {history.map((h) => (
              <li key={h.changed_at}>{new Date(h.changed_at).toLocaleString(locale)}: {h.changed.join(", ")}</li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
