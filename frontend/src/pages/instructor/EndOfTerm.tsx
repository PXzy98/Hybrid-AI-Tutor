import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { api, type Course } from "@/api/endpoints";
import { ErrorNote } from "@/components/common";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useI18n } from "@/i18n";

/** End of term: the instructor can first take an export and check it (nothing is deleted); ending the term
 * writes a final export and then deletes the course's student data. The instructor confirms by typing the
 * course code; exports can be downloaded until they expire. */
export default function EndOfTerm({ course }: { course: Course }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const end = useMutation({
    mutationFn: () => api.endTerm(course.id),
    onSuccess: () => {
      setOpen(false);
      setTyped("");
      qc.invalidateQueries({ queryKey: ["members", course.id] });
    },
  });
  const save = useMutation({
    mutationFn: async (exportId: string) => {
      const { blob, filename } = await api.downloadExport(course.id, exportId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    },
  });
  const early = useMutation({ mutationFn: () => api.createExport(course.id) });
  const done = end.data;
  return (
    <div className="space-y-4">
      {!done && (
        <Card>
          <CardHeader>
            <CardTitle>{t("end.previewTitle")}</CardTitle>
            <CardDescription>{t("end.previewIntro")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button type="button" variant="outline" onClick={() => early.mutate()} disabled={early.isPending}>
              {early.isPending ? t("end.working") : t("end.previewCreate")}
            </Button>
            <ErrorNote error={early.error} />
            {early.data && (
              <div role="status" className="space-y-2 text-sm">
                <p>{t("end.previewReady", { exported: early.data.students_exported })}</p>
                <p>{t("end.expires", { date: new Date(early.data.expires_at).toLocaleString() })}</p>
                <Button type="button" onClick={() => save.mutate(early.data.export_id)} disabled={save.isPending}>
                  <Download aria-hidden />{t("end.download")}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}
      <Card>
        <CardHeader>
          <CardTitle>{t("end.title")}</CardTitle>
          <CardDescription>{t("end.intro")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <ul className="list-disc space-y-1 pl-5 text-sm">
            <li>{t("end.step1")}</li><li>{t("end.step2")}</li><li>{t("end.step3")}</li>
          </ul>
          {!done && (
            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger asChild><Button type="button" variant="destructive">{t("end.start")}</Button></DialogTrigger>
              <DialogContent>
                <form onSubmit={(e) => { e.preventDefault(); end.mutate(); }} className="grid gap-4">
                  <DialogHeader>
                    <DialogTitle className="flex items-center gap-2"><TriangleAlert aria-hidden className="size-5 text-destructive" />{t("end.confirmTitle")}</DialogTitle>
                    <DialogDescription>{t("end.confirmBody", { code: course.code })}</DialogDescription>
                  </DialogHeader>
                  <div className="grid gap-1.5">
                    <Label htmlFor="end-code">{t("end.typeCode", { code: course.code })}</Label>
                    <Input id="end-code" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
                  </div>
                  <ErrorNote error={end.error} />
                  <DialogFooter>
                    <DialogClose asChild><Button type="button" variant="outline">{t("end.cancel")}</Button></DialogClose>
                    <Button type="submit" variant="destructive" disabled={typed.trim() !== course.code || end.isPending}>
                      {end.isPending ? t("end.working") : t("end.confirm")}
                    </Button>
                  </DialogFooter>
                </form>
              </DialogContent>
            </Dialog>
          )}
        </CardContent>
      </Card>
      {done && (
        <Alert variant="info" role="status" className="space-y-3">
          <p className="font-medium">{t("end.done")}</p>
          <p>{t("end.result", { exported: done.students_exported, removed: done.students_removed })}</p>
          <p>{t("end.expires", { date: new Date(done.expires_at).toLocaleString() })}</p>
          <Button type="button" onClick={() => save.mutate(done.export_id)} disabled={save.isPending}><Download aria-hidden />{t("end.download")}</Button>
          <ErrorNote error={save.error} />
        </Alert>
      )}
    </div>
  );
}
