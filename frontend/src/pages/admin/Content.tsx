import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";

import { admin, type ContentStatus } from "../../api/endpoints";

type RagMaterial = NonNullable<ContentStatus["topics"][number]["rag_materials"]>[number];

const kb = (n: number) => (n < 1024 * 1024 ? `${Math.ceil(n / 1024)} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`);

function Upload({ topic }: { topic: string }) {
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [replace, setReplace] = useState(false);
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
      <label className="sr-only" htmlFor={`file-${topic}`}>Course material file</label>
      <input id={`file-${topic}`} type="file" accept=".md,.txt,.pdf,.html,.htm,.docx"
             onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      <label className="flex items-center gap-1">
        <input type="checkbox" checked={replace} onChange={(e) => setReplace(e.target.checked)} />
        Replace a file with the same name
      </label>
      <button type="submit" className="btn-secondary py-1" disabled={!file || up.isPending}>Upload</button>
      {up.isSuccess && (
        <span role="status" className="text-teal-800">
          {up.data.ingested ? "Uploaded and searchable." : "File saved, but not searchable."}
          {up.data.ingest_error && <span className="ml-1 text-amber-800">{up.data.ingest_error}</span>}
        </span>
      )}
      {up.isError && <span role="alert" className="text-rose-700">{(up.error as Error).message}</span>}
    </form>
  );
}

function MaterialList({ materials, empty }: { materials: RagMaterial[]; empty: string }) {
  if (!materials.length) return <p className="text-sm text-slate-600">{empty}</p>;
  return (
    <ul className="space-y-2 text-sm">
      {materials.map((m) => (
        <li key={m.source} className="break-words">
          <span className="font-medium">{m.name}</span>
          <span className={m.indexed ? "ml-2 text-teal-800" : "ml-2 text-amber-800"}>
            {m.indexed ? `Searchable · ${m.passage_count} passages` : "Not searchable"}
          </span>
          {m.source.startsWith("https://") && <a href={m.source} target="_blank" rel="noreferrer" className="ml-2 underline">Source</a>}
          {m.message && <p className="text-amber-800">{m.message}</p>}
        </li>
      ))}
    </ul>
  );
}

/** Review status of the content (only reviewed items and corrections reach students) and course materials. */
export default function ContentPage() {
  const content = useQuery({ queryKey: ["admin", "content"], queryFn: admin.content });
  if (content.isLoading) return <p className="text-sm text-slate-600">Loading…</p>;
  if (content.isError || !content.data) return <p role="alert" className="text-sm text-rose-700">Could not load the content status.</p>;
  const c = content.data;
  return (
    <div className="space-y-4">
      {c.serve_unreviewed && (
        <p role="note" className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          Development mode: unreviewed check questions and corrections are shown to students
          (<code>content.serve_unreviewed</code>). Turn it off before real students use the tutor.
        </p>
      )}
      {c.topics.map((t) => (
        <section key={t.topic} className="card" aria-labelledby={`c-${t.topic}`}>
          <h2 id={`c-${t.topic}`} className="mb-2 font-semibold">{t.name}</h2>
          <dl className="grid grid-cols-3 gap-3 text-sm">
            <div><dt className="text-slate-600">Knowledge components</dt><dd>{t.kcs}</dd></div>
            <div><dt className="text-slate-600">Check questions reviewed</dt><dd>{t.items_reviewed} of {t.items}</dd></div>
            <div><dt className="text-slate-600">Corrections reviewed</dt><dd>{t.misconceptions_reviewed} of {t.misconceptions}</dd></div>
          </dl>
          <h3 className="mt-4 text-sm font-semibold">Built-in materials</h3>
          <MaterialList materials={(t.rag_materials ?? []).filter((m) => m.origin === "builtin")} empty="No built-in materials are currently searchable." />
          <h3 className="mt-4 text-sm font-semibold">Uploaded materials</h3>
          {(t.rag_materials ?? []).some((m) => m.origin === "uploaded") ? (
            <MaterialList materials={(t.rag_materials ?? []).filter((m) => m.origin === "uploaded")} empty="No uploads yet." />
          ) : t.materials.length === 0 ? (
            <p className="text-sm text-slate-600">No uploads yet.</p>
          ) : (
            <ul className="text-sm">
              {t.materials.map((m) => (
                <li key={m.name}>{m.name} <span className="text-slate-500">({kb(m.size_bytes)}, {new Date(m.uploaded_at).toLocaleDateString()}) · Saved; search status unavailable</span></li>
              ))}
            </ul>
          )}
          <Upload topic={t.topic} />
        </section>
      ))}
    </div>
  );
}
