import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";

import { api, type Course, type Misconception } from "@/api/endpoints";
import { ErrorNote } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useI18n } from "@/i18n";

/** Misconceptions: the wrong ideas the tutor watches for, each with the correction it gives. Retire one instead of deleting it. */
export default function Misconceptions({ course }: { course: Course }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const kcs = useQuery({ queryKey: ["kcs", course.id], queryFn: () => api.kcs(course.id) });
  const list = useQuery({ queryKey: ["misconceptions", course.id], queryFn: () => api.misconceptions(course.id) });
  const retire = useMutation({
    mutationFn: (id: number) => api.updateMisconception(course.id, id, { status: "retired" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["misconceptions", course.id] }),
  });
  const kcName = (id: number) => kcs.data?.find((k) => k.id === id)?.name ?? "";
  return (
    <Card>
      <CardHeader><CardTitle>{t("misc.title")}</CardTitle><CardDescription>{t("misc.hint")}</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        <ErrorNote error={list.error ?? retire.error} />
        <ul className="divide-y text-sm">
          {list.data?.map((m) => (
            <li key={m.id} className="flex flex-wrap items-start justify-between gap-2 py-2">
              <span className="min-w-0">
                <span className="font-medium">{m.code}</span> {m.statement}{" "}
                <Badge variant={m.status === "active" ? "success" : "secondary"}>{t(`content.status.${m.status}`)}</Badge>
                <br /><span className="text-muted-foreground">{kcName(m.kc_id)} · {m.correction}</span>
              </span>
              <span className="flex shrink-0 gap-1">
                <MisconceptionDialog course={course} misconception={m} />
                {m.status !== "retired" && (
                  <Button type="button" size="sm" variant="outline" aria-label={t("content.retireFor", { name: m.code })}
                          onClick={() => retire.mutate(m.id)}>{t("content.retire")}</Button>
                )}
              </span>
            </li>
          ))}
          {list.data?.length === 0 && <li className="py-2 text-muted-foreground">{t("misc.none")}</li>}
        </ul>
        <MisconceptionDialog course={course} />
      </CardContent>
    </Card>
  );
}

/** Create (no misconception) or edit one. The code is fixed once created. */
function MisconceptionDialog({ course, misconception }: { course: Course; misconception?: Misconception }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const kcs = useQuery({ queryKey: ["kcs", course.id], queryFn: () => api.kcs(course.id) });
  const initial = { kc_id: misconception?.kc_id ?? 0, code: misconception?.code ?? "", statement: misconception?.statement ?? "",
    correction: misconception?.correction ?? "", status: (misconception?.status === "draft" ? "draft" : "active") as "draft" | "active" };
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(initial);
  const kcId = form.kc_id || kcs.data?.[0]?.id || 0;
  const save = useMutation({
    mutationFn: () => misconception
      ? api.updateMisconception(course.id, misconception.id, { kc_id: kcId, statement: form.statement, correction: form.correction,
          ...(misconception.status === "retired" ? {} : { status: form.status }) })
      : api.createMisconception(course.id, { ...form, kc_id: kcId }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["misconceptions", course.id] });
      setOpen(false);
      setForm(initial);
    },
  });
  const p = misconception ? `mc-${misconception.id}` : "mc-new";
  function submit(e: FormEvent) {
    e.preventDefault();
    save.mutate();
  }
  return (
    <Dialog open={open} onOpenChange={(next) => { setOpen(next); if (next) { setForm(initial); save.reset(); } }}>
      <DialogTrigger asChild>
        {misconception
          ? <Button type="button" size="sm" variant="outline" aria-label={t("misc.editFor", { name: misconception.code })}><Pencil aria-hidden />{t("models.edit")}</Button>
          : <Button type="button"><Plus aria-hidden />{t("misc.add")}</Button>}
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={submit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>{t(misconception ? "misc.editTitle" : "misc.add")}</DialogTitle>
            <DialogDescription>{t("misc.formHint")}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5"><Label htmlFor={`${p}-kc`}>{t("content.kc")}</Label>
            <Select id={`${p}-kc`} value={kcId} onChange={(e) => setForm({ ...form, kc_id: Number(e.target.value) })}>
              {kcs.data?.map((k) => <option key={k.id} value={k.id}>{k.code} {k.name}</option>)}
            </Select></div>
          <div className="grid gap-1.5"><Label htmlFor={`${p}-code`}>{t("misc.code")}</Label>
            <Input id={`${p}-code`} value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })}
                   required readOnly={!!misconception} pattern="[A-Za-z0-9._\-]{1,64}" /></div>
          <div className="grid gap-1.5"><Label htmlFor={`${p}-statement`}>{t("misc.statement")}</Label>
            <Textarea id={`${p}-statement`} value={form.statement} onChange={(e) => setForm({ ...form, statement: e.target.value })} required maxLength={2000} /></div>
          <div className="grid gap-1.5"><Label htmlFor={`${p}-correction`}>{t("misc.correction")}</Label>
            <Textarea id={`${p}-correction`} value={form.correction} onChange={(e) => setForm({ ...form, correction: e.target.value })} required maxLength={4000} /></div>
          {misconception?.status !== "retired" && (
            <div className="grid gap-1.5"><Label htmlFor={`${p}-status`}>{t("members.status")}</Label>
              <Select id={`${p}-status`} value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as "draft" | "active" })}>
                <option value="draft">{t("content.status.draft")}</option>
                <option value="active">{t("content.status.active")}</option>
              </Select></div>
          )}
          <ErrorNote error={save.error} />
          <DialogFooter><Button type="submit" disabled={save.isPending || !kcId}>{save.isPending ? t("settings.saving") : t("settings.save")}</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
