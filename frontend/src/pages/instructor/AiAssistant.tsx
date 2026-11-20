import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { api, type AiDraft, type AiDraftAccept, type AiDraftKind, type AiDraftStatus, type Course } from "@/api/endpoints";
import { ErrorNote, Loading, PageHeader, StatusText } from "@/components/common";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useI18n } from "@/i18n";
import type { MessageKey } from "@/i18n/en";
import AiEvaluation from "./AiEvaluation";

const KINDS: AiDraftKind[] = ["custom", "faq", "project_ideas", "sample_proposal", "kcs", "check_items", "misconceptions"];
const STATUSES: AiDraftStatus[] = ["generating", "draft", "accepted", "discarded", "failed"];
const TIER1: AiDraftKind[] = ["faq", "project_ideas", "sample_proposal", "custom"];
// where the draft's material comes from (V5, V6)
const SOURCES = ["course", "module", "modules", "files", "upload", "url"] as const;
type SourceChoice = (typeof SOURCES)[number];

/** Instructor AI: drafts from the course material (tiers 1 and 2) and the cloud evaluation (tier 4). */
export default function AiAssistant({ course }: { course: Course }) {
  const { t } = useI18n();
  return (
    <div className="space-y-6">
      <PageHeader title={t("ai.title")} description={t("ai.intro")} />
      <Alert variant="info" role="note" icon>{t("ai.privacy")}</Alert>
      <Tabs defaultValue="drafts">
        <TabsList aria-label={t("ai.title")}>
          <TabsTrigger value="drafts">{t("ai.drafts")}</TabsTrigger>
          <TabsTrigger value="evaluation">{t("ai.evaluation")}</TabsTrigger>
        </TabsList>
        <TabsContent value="drafts"><Drafts course={course} /></TabsContent>
        <TabsContent value="evaluation"><AiEvaluation course={course} /></TabsContent>
      </Tabs>
    </div>
  );
}

function Drafts({ course }: { course: Course }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [filter, setFilter] = useState<AiDraftStatus | "">("");
  const [selected, setSelected] = useState<number | null>(null);
  const drafts = useQuery({ queryKey: ["ai-drafts", course.id, filter], queryFn: () => api.aiDrafts(course.id, filter || undefined) });
  return (
    <div className="space-y-4">
      <StartForm course={course} onStarted={(d) => { setSelected(d.id); qc.invalidateQueries({ queryKey: ["ai-drafts", course.id] }); }} />
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <CardTitle>{t("ai.list")}</CardTitle>
            <div className="grid gap-1.5">
              <Label htmlFor="ai-filter">{t("ai.filter")}</Label>
              <Select id="ai-filter" value={filter} onChange={(e) => setFilter(e.target.value as AiDraftStatus | "")}>
                <option value="">{t("ai.allStatuses")}</option>
                {STATUSES.map((s) => <option key={s} value={s}>{t(`ai.status.${s}` as MessageKey)}</option>)}
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <ErrorNote error={drafts.error} />
          {drafts.data?.length === 0 && <p className="text-sm text-muted-foreground">{t("ai.none")}</p>}
          <ul className="divide-y">
            {drafts.data?.map((d) => (
              <li key={d.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                <span>#{d.id} {t(`ai.kind.${d.kind}` as MessageKey)} <DraftStatus status={d.status} /></span>
                <Button type="button" size="sm" variant="outline" aria-label={t("ai.openFor", { id: d.id })} onClick={() => setSelected(d.id)}>{t("ai.open")}</Button>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
      {selected !== null && <DraftDetail key={selected} course={course} id={selected} onGone={() => setSelected(null)} />}
    </div>
  );
}

function StartForm({ course, onStarted }: { course: Course; onStarted: (d: AiDraft) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const modules = useQuery({ queryKey: ["modules", course.id], queryFn: () => api.modules(course.id) });
  const materials = useQuery({ queryKey: ["materials", course.id], queryFn: () => api.materials(course.id) });
  // V8: "Draft extra material" on Class overview hands over a request and its module (router state)
  const location = useLocation();
  const navigate = useNavigate();
  const handed = (location.state as { draft?: { request: string; moduleId: number | null } } | null)?.draft;
  // read once into the form: a reload or Back does not fill it again
  useEffect(() => {
    if (handed) navigate(location.pathname + location.search, { replace: true, state: null });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const [kind, setKind] = useState<AiDraftKind>("custom");
  const [request, setRequest] = useState(handed?.request ?? "");
  const [source, setSource] = useState<SourceChoice>(handed?.moduleId ? "module" : "course");
  const [moduleId, setModuleId] = useState<number | null>(handed?.moduleId ?? null);
  const [moduleIds, setModuleIds] = useState<number[]>([]);
  const [materialIds, setMaterialIds] = useState<number[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [pageUrl, setPageUrl] = useState("");
  const [addToCourse, setAddToCourse] = useState(false);
  const [addModuleId, setAddModuleId] = useState<number | null>(null); // where the uploaded file goes
  const [focus, setFocus] = useState("");
  // V16: the cloud model for public material, only with the explicit confirmation below
  const [cloud, setCloud] = useState(false);
  const [confirmCloud, setConfirmCloud] = useState(false);
  const cloudOffered = !course.local_only && !!course.cloud_available;  // else the model choice is hidden
  const useCloud = cloud && confirmCloud && cloudOffered;
  const model = useCloud ? { model: "cloud" as const, confirm_cloud: true } : {};
  const start = useMutation({
    mutationFn: () => {
      const text = kind === "custom" ? request : "";
      if (source === "upload" && file) {
        return api.createAiDraftFromUpload(course.id, { file, kind, request: text, focus, addToCourse, moduleId: addToCourse ? addModuleId : null, cloud: useCloud });
      }
      if (source === "url") {
        return api.createAiDraftFromUrl(course.id, { url: pageUrl.trim(), kind, request: text, focus, add_to_course: addToCourse,
                                                     module_id: addToCourse ? moduleId : null, ...model });
      }
      return api.createAiDraft(course.id, {
        kind, focus, request: text,
        module_id: source === "module" ? moduleId : null,
        ...(source === "modules" ? { module_ids: moduleIds } : {}),
        ...(source === "files" ? { material_ids: materialIds } : {}),
        ...model,
      });
    },
    onSuccess: (d) => {
      if (source === "upload" && addToCourse) qc.invalidateQueries({ queryKey: ["materials", course.id] });
      onStarted(d);
    },
  });
  const toggle = (list: number[], set: (v: number[]) => void, id: number) =>
    set(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);
  const moduleName = new Map((modules.data ?? []).map((m) => [m.id, m.title]));
  const missing = (kind === "custom" && !request.trim())
    || (source === "modules" && moduleIds.length === 0) || (source === "files" && materialIds.length === 0)
    || (cloud && cloudOffered && !confirmCloud) || (source === "upload" && !file) || (source === "url" && !pageUrl.trim()) || (source === "module" && moduleId === null);
  function submit(e: FormEvent) {
    e.preventDefault();
    if (!missing) start.mutate();
  }
  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2"><Sparkles aria-hidden className="size-4" />{t("ai.start")}</CardTitle><CardDescription>{t("ai.startHint")}</CardDescription></CardHeader>
      <CardContent>
        <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2" aria-label={t("ai.start")}>
          <div className="grid gap-1.5"><Label htmlFor="ai-kind">{t("ai.kindLabel")}</Label>
            <Select id="ai-kind" value={kind} onChange={(e) => setKind(e.target.value as AiDraftKind)}>
              {KINDS.map((k) => <option key={k} value={k}>{t(`ai.kind.${k}` as MessageKey)}</option>)}
            </Select></div>
          {kind === "custom" && (
            <div className="grid gap-1.5 sm:col-span-2"><Label htmlFor="ai-request">{t("ai.request")}</Label>
              <Textarea id="ai-request" value={request} maxLength={1000} required onChange={(e) => setRequest(e.target.value)}
                        placeholder={t("ai.requestHint")} aria-describedby="ai-request-examples" />
              <p id="ai-request-examples" className="text-xs text-muted-foreground">{t("ai.requestExamples")}</p></div>
          )}
          <fieldset className="grid gap-2 sm:col-span-2">
            <legend className="mb-1 text-sm font-medium">{t("ai.sourcesChoice")}</legend>
            <div className="flex flex-wrap gap-x-4 gap-y-1.5">
              {SOURCES.map((s) => (
                <label key={s} className="flex items-center gap-2 text-sm">
                  <input type="radio" name="ai-source" className="accent-primary" checked={source === s} onChange={() => setSource(s)} />
                  {t(`ai.source.${s}` as MessageKey)}
                </label>
              ))}
            </div>
            {source === "module" && (
              <Select aria-label={t("content.module")} value={moduleId ?? ""} onChange={(e) => setModuleId(e.target.value ? Number(e.target.value) : null)}>
                <option value="">{t("ai.chooseModule")}</option>
                {modules.data?.map((m) => <option key={m.id} value={m.id}>{m.title}</option>)}
              </Select>
            )}
            {source === "modules" && (
              <div className="grid gap-1 rounded-md border p-2 sm:grid-cols-2" role="group" aria-label={t("ai.source.modules")}>
                {modules.data?.map((m) => (
                  <label key={m.id} className="flex items-center gap-2 text-sm">
                    <input type="checkbox" className="accent-primary" checked={moduleIds.includes(m.id)} onChange={() => toggle(moduleIds, setModuleIds, m.id)} />
                    {m.title}
                  </label>
                ))}
              </div>
            )}
            {source === "files" && (
              <div className="grid max-h-56 gap-1 overflow-y-auto rounded-md border p-2" role="group" aria-label={t("ai.source.files")}>
                {(materials.data?.materials ?? []).map((m) => (
                  <label key={m.id} className="flex min-w-0 items-center gap-2 text-sm">
                    <input type="checkbox" className="accent-primary" checked={materialIds.includes(m.id)} onChange={() => toggle(materialIds, setMaterialIds, m.id)} />
                    <span className="min-w-0 break-words">{m.filename}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">{m.module_id === null ? t("nav.wholeCourse") : moduleName.get(m.module_id) ?? ""}</span>
                  </label>
                ))}
                {materials.data?.materials.length === 0 && <p className="text-sm text-muted-foreground">{t("ai.noFiles")}</p>}
              </div>
            )}
            {(source === "upload" || source === "url") && (
              <div className="grid gap-2 rounded-md border p-3">
                {source === "upload" ? (
                  <>
                    <Label htmlFor="ai-file">{t("ai.uploadFile")}</Label>
                    <Input id="ai-file" type="file" accept=".pdf,.pptx,.docx,.md,.txt,.html" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
                    <p className="text-xs text-muted-foreground">{t("ai.uploadHint")}</p>
                  </>
                ) : (
                  <>
                    <Label htmlFor="ai-url">{t("ai.pageUrl")}</Label>
                    <Input id="ai-url" type="url" inputMode="url" placeholder="https://" value={pageUrl} onChange={(e) => setPageUrl(e.target.value)} />
                    <p className="text-xs text-muted-foreground">{t("ai.pageHint")}</p>
                  </>
                )}
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" className="accent-primary" checked={addToCourse} onChange={(e) => setAddToCourse(e.target.checked)} />
                  {t("ai.addToCourse")}
                </label>
                {addToCourse && (
                  <Select aria-label={t("ai.addToModule")} value={addModuleId ?? ""} onChange={(e) => setAddModuleId(e.target.value ? Number(e.target.value) : null)}>
                    <option value="">{t("nav.wholeCourse")}</option>
                    {modules.data?.map((m) => <option key={m.id} value={m.id}>{m.title}</option>)}
                  </Select>
                )}
              </div>
            )}
          </fieldset>
          {cloudOffered && (
            <fieldset className="grid gap-2 sm:col-span-2">
              <legend className="mb-1 text-sm font-medium">{t("ai.model")}</legend>
              <div className="flex flex-wrap gap-x-4 gap-y-1.5">
                <label className="flex items-center gap-2 text-sm">
                  <input type="radio" name="ai-model" className="accent-primary" checked={!cloud} onChange={() => { setCloud(false); setConfirmCloud(false); }} />
                  {t("ai.modelLocal")}
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input type="radio" name="ai-model" className="accent-primary" checked={cloud} onChange={() => setCloud(true)} />
                  {t("ai.modelCloud")}
                </label>
              </div>
              {cloud && (
                <Alert variant="warning" icon>
                  <p>{t("ai.cloudNotice")}</p>
                  <label className="mt-2 flex items-start gap-2 text-sm font-medium">
                    <input type="checkbox" className="mt-0.5 accent-primary" checked={confirmCloud} onChange={(e) => setConfirmCloud(e.target.checked)} />
                    {t("ai.cloudConfirm")}
                  </label>
                </Alert>
              )}
            </fieldset>
          )}
          <div className="grid gap-1.5 sm:col-span-2"><Label htmlFor="ai-focus">{t("ai.focus")}</Label>
            <Input id="ai-focus" value={focus} maxLength={300} onChange={(e) => setFocus(e.target.value)} placeholder={t("ai.focusHint")} /></div>
          <div className="sm:col-span-2 space-y-2">
            <ErrorNote error={start.error} />
            <Button type="submit" disabled={start.isPending || missing}>{t("ai.startButton")}</Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function DraftDetail({ course, id, onGone }: { course: Course; id: number; onGone: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const draft = useQuery({
    queryKey: ["ai-draft", course.id, id],
    queryFn: () => api.aiDraft(course.id, id),
    refetchInterval: (q) => (q.state.data?.status === "generating" ? 1500 : false),
  });
  const [acceptedMsg, setAcceptedMsg] = useState("");
  const d = draft.data;
  if (draft.error) return <ErrorNote error={draft.error} />;
  if (!d) return <Loading variant="form" />;
  const refresh = (fresh: AiDraft) => {
    qc.setQueryData(["ai-draft", course.id, id], fresh);
    qc.invalidateQueries({ queryKey: ["ai-drafts", course.id] });
  };
  return (
    <Card aria-label={t("ai.detail", { id })}>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">#{d.id} {t(`ai.kind.${d.kind}` as MessageKey)}
          <DraftStatus status={d.status} /></CardTitle>
        <CardDescription>{d.status === "draft" ? t("ai.notVisible") : d.status === "accepted" ? t("ai.acceptedNote") : ""}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {d.status === "generating" && <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 aria-hidden className="size-4 animate-spin motion-reduce:animate-none" />{t("ai.generating")}</p>}
        {d.status === "failed" && <Alert variant="destructive" role="alert" icon>{t("ai.failed")}{d.error ? ` ${d.error}` : ""}</Alert>}
        {!!d.cited_sources.length && (
          <div className="text-sm">
            <p className="font-medium">{t("ai.sources")}</p>
            <ul className="list-disc pl-5 text-muted-foreground">{d.cited_sources.map((s) => <li key={s}>{s}</li>)}</ul>
          </div>
        )}
        {(d.status === "draft" || d.status === "accepted" || d.status === "discarded") && (
          <ContentEditor key={d.updated_at} course={course} draft={d} onSaved={refresh} />
        )}
        {acceptedMsg && <StatusText>{acceptedMsg}</StatusText>}
        {d.status === "draft" && <Actions course={course} draft={d} onAccepted={(out) => { setAcceptedMsg(`${t("ai.accepted", { n: Object.values(out.created).reduce((a, b) => a + b.length, 0) })}${out.rebuild_job_id ? ` ${t("ai.reindexing")}` : ""}`); refresh(out.draft); }} onGone={() => { qc.invalidateQueries({ queryKey: ["ai-drafts", course.id] }); onGone(); }} />}
      </CardContent>
    </Card>
  );
}

function ContentEditor({ course, draft, onSaved }: { course: Course; draft: AiDraft; onSaved: (d: AiDraft) => void }) {
  const { t } = useI18n();
  const editable = draft.status === "draft";
  const tier1 = TIER1.includes(draft.kind);
  const content = draft.content as { title?: string; body?: string };
  const [title, setTitle] = useState(content.title ?? "");
  const [body, setBody] = useState(content.body ?? "");
  const [json, setJson] = useState(() => JSON.stringify(draft.content, null, 2));
  const [parseError, setParseError] = useState("");
  const save = useMutation({
    mutationFn: () => {
      if (tier1) return api.updateAiDraft(course.id, draft.id, { title, body });
      return api.updateAiDraft(course.id, draft.id, JSON.parse(json));
    },
    onSuccess: onSaved,
  });
  function submit(e: FormEvent) {
    e.preventDefault();
    setParseError("");
    if (!tier1) {
      try { JSON.parse(json); } catch { setParseError(t("ai.badJson")); return; }
    }
    save.mutate();
  }
  return (
    <form onSubmit={submit} className="space-y-3" aria-label={t("ai.editor")}>
      {tier1 ? (
        <>
          <div className="grid gap-1.5"><Label htmlFor="ai-title">{t("course.title")}</Label>
            <Input id="ai-title" value={title} disabled={!editable} onChange={(e) => setTitle(e.target.value)} /></div>
          <div className="grid gap-1.5"><Label htmlFor="ai-body">{t("ai.body")}</Label>
            <Textarea id="ai-body" rows={12} value={body} disabled={!editable} onChange={(e) => setBody(e.target.value)} /></div>
        </>
      ) : (
        <div className="grid gap-1.5"><Label htmlFor="ai-json">{t("ai.items")}</Label>
          <p className="text-xs text-muted-foreground">{t("ai.itemsHint")}</p>
          <Textarea id="ai-json" rows={14} className="font-mono text-xs" value={json} disabled={!editable} onChange={(e) => setJson(e.target.value)} /></div>
      )}
      {parseError && <Alert variant="destructive" role="alert">{parseError}</Alert>}
      <ErrorNote error={save.error} />
      {save.isSuccess && <StatusText>{t("settings.saved")}</StatusText>}
      {editable && <Button type="submit" variant="outline" disabled={save.isPending}>{t("ai.saveChanges")}</Button>}
    </form>
  );
}

function Actions({ course, draft, onAccepted, onGone }: { course: Course; draft: AiDraft; onAccepted: (out: AiDraftAccept) => void; onGone: () => void }) {
  const { t } = useI18n();
  const modules = useQuery({ queryKey: ["modules", course.id], queryFn: () => api.modules(course.id) });
  const [moduleId, setModuleId] = useState<number | null>(null);
  const needsModule = draft.kind === "kcs" && draft.module_id === null;
  const needsPlace = TIER1.includes(draft.kind) && draft.module_id === null;
  const accept = useMutation({
    mutationFn: () => api.acceptAiDraft(course.id, draft.id, moduleId),
    onSuccess: onAccepted,
  });
  const discard = useMutation({ mutationFn: () => api.discardAiDraft(course.id, draft.id), onSuccess: onGone });
  return (
    <div className="space-y-3 border-t pt-4">
      {(needsModule || needsPlace) && (
        <div className="grid gap-1.5 sm:max-w-sm">
          <Label htmlFor="ai-accept-module">{needsModule ? t("ai.acceptModule") : t("ai.acceptPlace")}</Label>
          <Select id="ai-accept-module" value={moduleId ?? ""} onChange={(e) => setModuleId(e.target.value ? Number(e.target.value) : null)}>
            <option value="">{needsModule ? t("ai.chooseModule") : t("nav.wholeCourse")}</option>
            {modules.data?.map((m) => <option key={m.id} value={m.id}>{m.title}</option>)}
          </Select>
        </div>
      )}
      <p className="text-sm text-muted-foreground">{t("ai.acceptHint")}</p>
      <ErrorNote error={accept.error ?? discard.error} />
      <div className="flex flex-wrap gap-3">
        <Button type="button" onClick={() => accept.mutate()} disabled={accept.isPending}>{t("ai.accept")}</Button>
        <Button type="button" variant="outline" onClick={() => discard.mutate()} disabled={discard.isPending}>{t("ai.discard")}</Button>
      </div>
    </div>
  );
}

const DRAFT_VARIANT: Record<AiDraftStatus, "secondary" | "info" | "success" | "destructive"> = {
  generating: "secondary", draft: "info", accepted: "success", discarded: "secondary", failed: "destructive",
};

/** The state of a draft: text, with a spinner while it is being written. */
function DraftStatus({ status }: { status: AiDraftStatus }) {
  const { t } = useI18n();
  return (
    <Badge variant={DRAFT_VARIANT[status]}>
      {status === "generating" && <Loader2 aria-hidden className="animate-spin motion-reduce:animate-none" />}
      {t(`ai.status.${status}` as MessageKey)}
    </Badge>
  );
}
