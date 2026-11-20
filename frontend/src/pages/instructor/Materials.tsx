import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileStack, FileText, Loader2, Trash2, Upload } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { api, type Course, type Material } from "@/api/endpoints";
import { EmptyState, ErrorNote, Loading, PageHeader } from "@/components/common";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useI18n } from "@/i18n";
import type { MessageKey } from "@/i18n/en";

/** Course materials: upload (privacy-scanned by the server), delete, and the state of the search index. */
export default function Materials({ course }: { course: Course }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const materials = useQuery({ queryKey: ["materials", course.id], queryFn: () => api.materials(course.id) });
  const modules = useQuery({ queryKey: ["modules", course.id], queryFn: () => api.modules(course.id) });
  const jobId = materials.data?.rebuild_job_id ?? null;
  const job = useQuery({
    queryKey: ["job", course.id, jobId],
    queryFn: () => api.job(course.id, jobId as number),
    enabled: jobId !== null,
    refetchInterval: (q) => (q.state.data && (q.state.data.status === "done" || q.state.data.status === "failed") ? false : 1500),
  });
  const jobStatus = job.data?.status;
  const rebuilding = jobId !== null && jobStatus !== "done" && jobStatus !== "failed";
  useEffect(() => {
    if (jobStatus === "done" || jobStatus === "failed") qc.invalidateQueries({ queryKey: ["materials", course.id] });
  }, [jobStatus, course.id, qc]);

  const refresh = () => qc.invalidateQueries({ queryKey: ["materials", course.id] });
  const [pendingDelete, setPendingDelete] = useState<Material | null>(null);
  const remove = useMutation({
    mutationFn: (m: Material) => api.deleteMaterial(course.id, m.id),
    onSuccess: () => { setPendingDelete(null); refresh(); },
  });
  const refetch = useMutation({ mutationFn: (m: Material) => api.refetchMaterial(course.id, m.id), onSuccess: refresh });
  const moduleName = (id: number | null) => (id === null ? t("materials.courseLevel") : modules.data?.find((m) => m.id === id)?.title ?? String(id));

  return (
    <div className="space-y-6">
      <PageHeader title={t("materials.title")} description={t("materials.intro")} />
      <ErrorNote error={materials.error} />
      {rebuilding && (
        <Alert variant="info" role="status" className="flex items-center gap-2">
          <Loader2 aria-hidden className="size-4 animate-spin motion-reduce:animate-none text-info" />{t("materials.rebuilding")}
        </Alert>
      )}
      {jobStatus === "failed" && <Alert variant="destructive" role="alert" icon>{t("materials.rebuildFailed")}</Alert>}
      <section aria-labelledby="mat-list" className="space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 id="mat-list" className="text-sm font-semibold">{t("materials.list", { n: materials.data?.materials.length ?? 0 })}</h3>
          {materials.data && <p className="text-xs text-muted-foreground">{t("materials.indexVersion", { n: materials.data.index_version })}</p>}
        </div>
        {materials.isLoading && <Loading variant="table" />}
        {materials.data?.materials.length === 0 && <EmptyState icon={FileStack} title={t("empty.materials.title")}>{t("materials.none")}</EmptyState>}
        {!!materials.data?.materials.length && (
          <Table>
            <TableHeader><TableRow>
              <TableHead>{t("materials.file")}</TableHead><TableHead className="hidden sm:table-cell">{t("content.module")}</TableHead>
              <TableHead className="hidden sm:table-cell">{t("materials.size")}</TableHead><TableHead>{t("members.status")}</TableHead>
              <TableHead><span className="sr-only">{t("students.actions")}</span></TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {materials.data.materials.map((m) => (
                <TableRow key={m.id}>
                  <TableCell>
                    <span className="flex items-center gap-2.5 font-medium">
                      <span aria-hidden className="flex size-7 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground"><FileText className="size-4" /></span>
                      <span className="max-w-64 min-w-0 break-words">{m.filename}</span>
                    </span>
                    {/* V17 W14: on a phone the module is shown under the file name instead of in a column off screen */}
                    <span className="mt-1 block text-xs text-muted-foreground sm:hidden">{moduleName(m.module_id)}</span>
                    {m.source_url && (isHttps(m.source_url) ? (
                      <a href={m.source_url} target="_blank" rel="noopener noreferrer nofollow" className="mt-1 block max-w-64 break-words text-xs text-muted-foreground underline underline-offset-2">{m.source_url}</a>
                    ) : (
                      <span className="mt-1 block max-w-64 break-words text-xs text-muted-foreground">{m.source_url}</span>
                    ))}
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">{moduleName(m.module_id)}</TableCell>
                  <TableCell className="hidden tabular-nums text-muted-foreground sm:table-cell">{Math.max(1, Math.round(m.size_bytes / 1024))} KB</TableCell>
                  <TableCell><Badge variant={scanVariant(m.scan_status)}>{SCAN_STATES.includes(m.scan_status) ? t(`materials.scan.${m.scan_status}` as MessageKey) : m.scan_status}</Badge></TableCell>
                  <TableCell className="text-right">
                    {m.source_url && (
                      <Button type="button" size="sm" variant="ghost" loading={refetch.isPending && refetch.variables?.id === m.id}
                              aria-label={t("materials.refetchFor", { name: m.filename })} onClick={() => refetch.mutate(m)}>{t("materials.refetch")}</Button>
                    )}
                    <Button type="button" size="icon-sm" variant="ghost" className="text-muted-foreground hover:text-destructive" aria-label={t("materials.deleteFor", { name: m.filename })} onClick={() => setPendingDelete(m)}><Trash2 aria-hidden /></Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>
      <ErrorNote error={refetch.error} />
      <UploadCard course={course} modules={modules.data ?? []} onDone={refresh} />
      <WebPageCard course={course} modules={modules.data ?? []} onDone={refresh} />
      <Dialog open={!!pendingDelete} onOpenChange={(o) => { if (!o) setPendingDelete(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("materials.deleteTitle")}</DialogTitle>
            <DialogDescription>{t("materials.deleteBody", { name: pendingDelete?.filename ?? "" })}</DialogDescription>
          </DialogHeader>
          <ErrorNote error={remove.error} />
          <DialogFooter>
            <DialogClose asChild><Button type="button" variant="outline">{t("end.cancel")}</Button></DialogClose>
            <Button type="button" variant="destructive" loading={remove.isPending} onClick={() => pendingDelete && remove.mutate(pendingDelete)}>{t("materials.delete")}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function UploadCard({ course, modules, onDone }: { course: Course; modules: { id: number; title: string }[]; onDone: () => void }) {
  const { t } = useI18n();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [moduleId, setModuleId] = useState<number | null>(null);
  const [over, setOver] = useState(false);
  const upload = useMutation({
    mutationFn: (f: File) => api.uploadMaterial(course.id, f, moduleId),
    onSuccess: () => { setFile(null); if (input.current) input.current.value = ""; onDone(); },
  });
  function submit(e: FormEvent) {
    e.preventDefault();
    if (file) upload.mutate(file);
  }
  return (
    <Card>
      <CardHeader><CardTitle>{t("materials.upload")}</CardTitle><CardDescription>{t("materials.uploadHint")}</CardDescription></CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-1.5 sm:col-span-2">
              <Label htmlFor="mat-file">{t("materials.file")}</Label>
              <div onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
                   onDrop={(e) => {
                     e.preventDefault();
                     setOver(false);
                     const dropped = e.dataTransfer.files?.[0];
                     if (!dropped) return;
                     if (input.current) input.current.files = e.dataTransfer.files;
                     setFile(dropped);
                   }}
                   className={`flex flex-col items-center gap-2 rounded-lg border-2 border-dashed px-4 py-6 text-center transition-colors ${over ? "border-primary bg-primary-soft" : "border-input"}`}>
                <Upload aria-hidden className="size-5 text-muted-foreground" />
                <Input id="mat-file" ref={input} type="file" accept=".pdf,.pptx,.docx,.md,.txt,.html,.htm"
                       className="h-auto max-w-sm cursor-pointer border-0 bg-transparent p-0 text-center file:mr-3 file:rounded-md file:border-0 file:bg-secondary file:px-3 file:py-1.5 file:text-sm file:font-medium"
                       onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
              </div>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="mat-module">{t("content.module")}</Label>
              <Select id="mat-module" value={moduleId ?? ""} onChange={(e) => setModuleId(e.target.value ? Number(e.target.value) : null)}>
                <option value="">{t("materials.courseLevel")}</option>
                {modules.map((m) => <option key={m.id} value={m.id}>{m.title}</option>)}
              </Select>
            </div>
          </div>
          <ErrorNote error={upload.error} />
          <Button loading={upload.isPending} type="submit" disabled={!file || upload.isPending}>{upload.isPending ? t("materials.uploading") : t("materials.uploadButton")}</Button>
        </form>
      </CardContent>
    </Card>
  );
}

/** V7: a web page as course material. The server fetches it (https, public addresses only, size and time
 *  limits), keeps its address and scans it like an upload. */
function WebPageCard({ course, modules, onDone }: { course: Course; modules: { id: number; title: string }[]; onDone: () => void }) {
  const { t } = useI18n();
  const [url, setUrl] = useState("");
  const [moduleId, setModuleId] = useState<number | null>(null);
  const add = useMutation({ mutationFn: () => api.addUrlMaterial(course.id, url.trim(), moduleId), onSuccess: () => { setUrl(""); onDone(); } });
  function submit(e: FormEvent) {
    e.preventDefault();
    if (url.trim()) add.mutate();
  }
  return (
    <Card>
      <CardHeader><CardTitle>{t("materials.webTitle")}</CardTitle><CardDescription>{t("materials.webHint")}</CardDescription></CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-1.5 sm:col-span-2">
              <Label htmlFor="mat-url">{t("materials.webUrl")}</Label>
              <Input id="mat-url" type="url" inputMode="url" placeholder="https://" value={url} onChange={(e) => setUrl(e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="mat-url-module">{t("materials.webModule")}</Label>
              <Select id="mat-url-module" value={moduleId ?? ""} onChange={(e) => setModuleId(e.target.value ? Number(e.target.value) : null)}>
                <option value="">{t("materials.courseLevel")}</option>
                {modules.map((m) => <option key={m.id} value={m.id}>{m.title}</option>)}
              </Select>
            </div>
          </div>
          <ErrorNote error={add.error} />
          <Button loading={add.isPending} type="submit" disabled={!url.trim() || add.isPending}>{t("materials.webAdd")}</Button>
        </form>
      </CardContent>
    </Card>
  );
}

const SCAN_STATES = ["pending", "accepted", "rejected"];

function scanVariant(status: string): "success" | "secondary" | "destructive" {
  if (status === "accepted") return "success";
  if (status === "infected" || status === "failed" || status === "rejected") return "destructive";
  return "secondary";
}

/** A link is made only for an https address: the address comes from the first line of a file. */
function isHttps(value: string): boolean {
  try {
    return new URL(value).protocol === "https:";
  } catch {
    return false;
  }
}
