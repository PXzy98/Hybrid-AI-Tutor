import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";

import { admin, type ContentStatus } from "../../api/endpoints";
import { useI18n } from "../../i18n";

type RagMaterial = NonNullable<ContentStatus["topics"][number]["rag_materials"]>[number];

const kb = (n: number) => (n < 1024 * 1024 ? `${Math.ceil(n / 1024)} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`);

function Upload({ topic }: { topic: string }) {
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [replace, setReplace] = useState(false);
  const { t } = useI18n();
  const up = useMutation({
    mutationFn: () => admin.uploadMaterial(topic, file!, replace),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "content"] }),
  });
  function submit(e: FormEvent) {
    e.preventDefault();
    if (file) up.mutate();
  }
  return (
    <form onSubmit={submit} className="mt-3 flex flex-wrap items-center gap-3 text-sm">
      <label className="sr-only" htmlFor={`file-${topic}`}>{t("content.file")}</label>
      <input id={`file-${topic}`} type="file" accept=".md,.txt,.pdf,.html,.htm,.docx"
             onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      <label className="flex items-center gap-1">
        <input type="checkbox" checked={replace} onChange={(e) => setReplace(e.target.checked)} />
        {t("content.replace")}
      </label>
      <button type="submit" className="btn-secondary py-1" disabled={!file || up.isPending}>{t("content.upload")}</button>
      {up.isSuccess && (
        <span role="status" className="text-teal-800">
          {up.data.ingested ? t("content.ingested") : t("content.notIngested")}
          {up.data.ingest_error && <span className="ml-1 text-amber-800">{up.data.ingest_error}</span>}
        </span>
      )}
      {up.isError && <span role="alert" className="text-rose-700">{(up.error as Error).message}</span>}
    </form>
  );
}

function MaterialList({ materials, empty }: { materials: RagMaterial[]; empty: string }) {
  const { t } = useI18n();
  if (!materials.length) return <p className="text-sm text-slate-600">{empty}</p>;
  return (
    <ul className="space-y-2 text-sm">
      {materials.map((m) => (
        <li key={m.source} className="break-words">
          <span className="font-medium">{m.name}</span>
          <span className={m.indexed ? "ml-2 text-teal-800" : "ml-2 text-amber-800"}>
            {m.indexed ? t("content.searchable", { n: m.passage_count ?? 0 }) : t("content.notSearchable")}
          </span>
          {m.source.startsWith("https://") && <a href={m.source} target="_blank" rel="noreferrer" className="ml-2 underline">{t("content.source")}</a>}
          {m.message && <p className="text-amber-800">{m.message}</p>}
        </li>
      ))}
    </ul>
  );
}

/** Review status of the content (only reviewed items and corrections reach students) and course materials. */
export default function ContentPage() {
  const content = useQuery({ queryKey: ["admin", "content"], queryFn: admin.content });
  const { t: tr, locale } = useI18n();
  if (content.isLoading) return <p className="text-sm text-slate-600">{tr("app.loading")}</p>;
  if (content.isError || !content.data) return <p role="alert" className="text-sm text-rose-700">{tr("content.loadError")}</p>;
  const c = content.data;
  return (
    <div className="space-y-4">
      {c.serve_unreviewed && (
        <p role="note" className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {tr("content.devMode", { setting: "content.serve_unreviewed" })}
        </p>
      )}
      {c.topics.map((t) => (
        <section key={t.topic} className="card" aria-labelledby={`c-${t.topic}`}>
          <h2 id={`c-${t.topic}`} className="mb-2 font-semibold">{t.name}</h2>
          <dl className="grid grid-cols-3 gap-3 text-sm">
            <div><dt className="text-slate-600">{tr("content.kcs")}</dt><dd>{t.kcs}</dd></div>
            <div><dt className="text-slate-600">{tr("content.itemsReviewed")}</dt><dd>{tr("content.ofTotal", { n: t.items_reviewed, total: t.items })}</dd></div>
            <div><dt className="text-slate-600">{tr("content.correctionsReviewed")}</dt><dd>{tr("content.ofTotal", { n: t.misconceptions_reviewed, total: t.misconceptions })}</dd></div>
          </dl>
          <h3 className="mt-4 text-sm font-semibold">{tr("content.builtin")}</h3>
          <MaterialList materials={(t.rag_materials ?? []).filter((m) => m.origin === "builtin")} empty={tr("content.noBuiltin")} />
          <h3 className="mt-4 text-sm font-semibold">{tr("content.uploaded")}</h3>
          {(t.rag_materials ?? []).some((m) => m.origin === "uploaded") ? (
            <MaterialList materials={(t.rag_materials ?? []).filter((m) => m.origin === "uploaded")} empty={tr("content.noUploads")} />
          ) : t.materials.length === 0 ? (
            <p className="text-sm text-slate-600">{tr("content.noUploads")}</p>
          ) : (
            <ul className="text-sm">
              {t.materials.map((m) => (
                <li key={m.name}>{m.name} <span className="text-slate-500">({kb(m.size_bytes)}, {new Date(m.uploaded_at).toLocaleDateString(locale)}) · {tr("content.savedNoStatus")}</span></li>
              ))}
            </ul>
          )}
          <Upload topic={t.topic} />
        </section>
      ))}
    </div>
  );
}
