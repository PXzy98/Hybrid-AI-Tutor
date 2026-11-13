import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, Upload } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";

import { api, type Course } from "@/api/endpoints";
import { ErrorNote } from "@/components/common";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useI18n } from "@/i18n";

/** Export the course content as a ZIP of YAML files, or import one into a course that has no content yet. */
export default function ContentTransfer({ course }: { course: Course }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const exportAll = useMutation({
    mutationFn: async () => {
      const { blob, filename } = await api.exportContent(course.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    },
  });
  const importAll = useMutation({
    mutationFn: (f: File) => api.importContent(course.id, f),
    onSuccess: () => {
      if (input.current) input.current.value = "";
      setFile(null);
      for (const key of ["modules", "kcs", "check-items", "misconceptions"]) qc.invalidateQueries({ queryKey: [key, course.id] });
    },
  });
  function submit(e: FormEvent) {
    e.preventDefault();
    if (file) importAll.mutate(file);
  }
  const done = importAll.data;
  return (
    <Card>
      <CardHeader><CardTitle>{t("transfer.title")}</CardTitle><CardDescription>{t("transfer.hint")}</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Button type="button" variant="outline" onClick={() => exportAll.mutate()} disabled={exportAll.isPending}>
            <Download aria-hidden />{t("transfer.export")}
          </Button>
          <ErrorNote error={exportAll.error} />
        </div>
        <form onSubmit={submit} className="grid gap-2 border-t pt-4" aria-label={t("transfer.import")}>
          <Label htmlFor="content-file">{t("transfer.file")}</Label>
          <Input id="content-file" ref={input} type="file" accept=".zip,application/zip" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <div><Button type="submit" disabled={!file || importAll.isPending}><Upload aria-hidden />{t("transfer.import")}</Button></div>
          <ErrorNote error={importAll.error} />
          {done && (
            <Alert variant="info" role="status">
              {t("transfer.done", { modules: done.modules, kcs: done.kcs, items: done.items, misconceptions: done.misconceptions })}
            </Alert>
          )}
        </form>
      </CardContent>
    </Card>
  );
}
