import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Loader2, Trash2 } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { api, type Course, type Material } from "@/api/endpoints";
import { ErrorNote } from "@/components/common";
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
  const moduleName = (id: number | null) => (id === null ? t("materials.courseLevel") : modules.data?.find((m) => m.id === id)?.title ?? String(id));

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">{t("materials.title")}</h2>
        <p className="text-sm text-muted-foreground">{t("materials.intro")}</p>
      </div>
      <UploadCard course={course} modules={modules.data ?? []} onDone={refresh} />
      <ErrorNote error={materials.error} />
      {rebuilding && (
        <Alert variant="info" role="status" className="flex items-center gap-2">
          <Loader2 aria-hidden className="size-4 animate-spin" />{t("materials.rebuilding")}
        </Alert>
      )}
      {jobStatus === "failed" && <Alert variant="destructive" role="alert">{t("materials.rebuildFailed")}</Alert>}
      <Card>
        <CardHeader>
          <CardTitle>{t("materials.list", { n: materials.data?.materials.length ?? 0 })}</CardTitle>
          {materials.data && <CardDescription>{t("materials.indexVersion", { n: materials.data.index_version })}</CardDescription>}
        </CardHeader>
        <CardContent>
          {materials.data?.materials.length === 0 && <p className="text-sm text-muted-foreground">{t("materials.none")}</p>}
          {!!materials.data?.materials.length && (
            <Table>
              <TableHeader><TableRow>
                <TableHead>{t("materials.file")}</TableHead><TableHead>{t("content.module")}</TableHead>
                <TableHead>{t("materials.size")}</TableHead><TableHead>{t("members.status")}</TableHead>
                <TableHead><span className="sr-only">{t("students.actions")}</span></TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {materials.data.materials.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell className="font-medium"><FileText aria-hidden className="mr-1 inline size-4 text-muted-foreground" />{m.filename}</TableCell>
                    <TableCell>{moduleName(m.module_id)}</TableCell>
                    <TableCell className="tabular-nums">{Math.max(1, Math.round(m.size_bytes / 1024))} KB</TableCell>
                    <TableCell><Badge variant={m.scan_status === "clean" ? "success" : "secondary"}>{m.scan_status}</Badge></TableCell>
                    <TableCell className="text-right">
                      <Button type="button" size="icon" variant="ghost" aria-label={t("materials.deleteFor", { name: m.filename })} onClick={() => setPendingDelete(m)}><Trash2 aria-hidden /></Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
      <Dialog open={!!pendingDelete} onOpenChange={(o) => { if (!o) setPendingDelete(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("materials.deleteTitle")}</DialogTitle>
            <DialogDescription>{t("materials.deleteBody", { name: pendingDelete?.filename ?? "" })}</DialogDescription>
          </DialogHeader>
          <ErrorNote error={remove.error} />
          <DialogFooter>
            <DialogClose asChild><Button type="button" variant="outline">{t("end.cancel")}</Button></DialogClose>
            <Button type="button" variant="destructive" disabled={remove.isPending} onClick={() => pendingDelete && remove.mutate(pendingDelete)}>{t("materials.delete")}</Button>
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
            <div className="grid gap-1.5">
              <Label htmlFor="mat-file">{t("materials.file")}</Label>
              <Input id="mat-file" ref={input} type="file" accept=".pdf,.pptx,.docx,.md,.txt,.html,.htm" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
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
          <Button type="submit" disabled={!file || upload.isPending}>{upload.isPending ? t("materials.uploading") : t("materials.uploadButton")}</Button>
        </form>
      </CardContent>
    </Card>
  );
}
