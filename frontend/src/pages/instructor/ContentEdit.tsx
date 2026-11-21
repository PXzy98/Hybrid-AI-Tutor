import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Pencil } from "lucide-react";
import { useState, type FormEvent } from "react";

import { api, type CheckItemFull, type Course, type Kc } from "@/api/endpoints";
import { ErrorNote } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useI18n } from "@/i18n";

const CHOICES = ["A", "B", "C", "D"] as const;

/** Edit the wording of a knowledge component (V18): name and definition. The code, the module and the
 *  learners' records stay; a change of meaning is a retire and a new KC. */
export function KcEditDialog({ course, kc, onSaved }: { course: Course; kc: Kc; onSaved: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const initial = { name: kc.name, definition: kc.definition };
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(initial);
  const save = useMutation({
    mutationFn: () => api.updateKc(course.id, kc.id, form),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["kcs", course.id] });
      setOpen(false);
      onSaved();
    },
  });
  const p = `kc-${kc.id}`;
  function submit(e: FormEvent) {
    e.preventDefault();
    save.mutate();
  }
  return (
    <Dialog open={open} onOpenChange={(next) => { setOpen(next); if (next) { setForm(initial); save.reset(); } }}>
      <DialogTrigger asChild>
        <Button type="button" size="sm" variant="outline" aria-label={t("content.editFor", { name: kc.name })}><Pencil aria-hidden />{t("models.edit")}</Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={submit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>{t("content.editKcTitle", { code: kc.code })}</DialogTitle>
            <DialogDescription>{t("content.editMeaningHint")}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5"><Label htmlFor={`${p}-name`}>{t("content.kcName")}</Label>
            <Input id={`${p}-name`} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required maxLength={200} /></div>
          <div className="grid gap-1.5"><Label htmlFor={`${p}-def`}>{t("content.definition")}</Label>
            <Textarea id={`${p}-def`} value={form.definition} onChange={(e) => setForm({ ...form, definition: e.target.value })} maxLength={4000} /></div>
          <ErrorNote error={save.error} />
          <DialogFooter><Button loading={save.isPending} type="submit" disabled={save.isPending || !form.name.trim()}>{save.isPending ? t("settings.saving") : t("settings.save")}</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** Edit the wording of a check item (V18): question, option texts and explanation. The code, the knowledge
 *  component, the correct answer and the misconception tags of the options stay. */
export function ItemEditDialog({ course, item, onSaved }: { course: Course; item: CheckItemFull; onSaved: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const initial = {
    stem: item.stem, explanation: item.explanation,
    options: Object.fromEntries(CHOICES.map((c) => [c, item.options[c]?.text ?? ""])) as Record<(typeof CHOICES)[number], string>,
  };
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(initial);
  const save = useMutation({
    mutationFn: () => api.updateCheckItem(course.id, item.id, {
      stem: form.stem, explanation: form.explanation,
      options: Object.fromEntries(CHOICES.map((c) => [c, { text: form.options[c], misconception: item.options[c]?.misconception ?? null }])),
    }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["check-items", course.id] });
      setOpen(false);
      onSaved();
    },
  });
  const p = `it-${item.id}`;
  const blank = !form.stem.trim() || CHOICES.some((c) => !form.options[c].trim());
  function submit(e: FormEvent) {
    e.preventDefault();
    save.mutate();
  }
  return (
    <Dialog open={open} onOpenChange={(next) => { setOpen(next); if (next) { setForm(initial); save.reset(); } }}>
      <DialogTrigger asChild>
        <Button type="button" size="sm" variant="outline" aria-label={t("content.editFor", { name: item.code })}><Pencil aria-hidden />{t("models.edit")}</Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={submit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>{t("content.editItemTitle", { code: item.code })}</DialogTitle>
            <DialogDescription>{t("content.editMeaningHint")}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5"><Label htmlFor={`${p}-stem`}>{t("content.stem")}</Label>
            <Textarea id={`${p}-stem`} value={form.stem} onChange={(e) => setForm({ ...form, stem: e.target.value })} required maxLength={2000} /></div>
          {CHOICES.map((c) => (
            <div key={c} className="grid gap-1.5">
              <Label htmlFor={`${p}-opt-${c}`}>{c === item.answer ? t("content.optionCorrect", { key: c }) : t("content.option", { key: c })}</Label>
              <Input id={`${p}-opt-${c}`} value={form.options[c]} onChange={(e) => setForm({ ...form, options: { ...form.options, [c]: e.target.value } })} required maxLength={1000} />
            </div>
          ))}
          <div className="grid gap-1.5"><Label htmlFor={`${p}-expl`}>{t("content.explanation")}</Label>
            <Textarea id={`${p}-expl`} value={form.explanation} onChange={(e) => setForm({ ...form, explanation: e.target.value })} maxLength={4000} /></div>
          <ErrorNote error={save.error} />
          <DialogFooter><Button loading={save.isPending} type="submit" disabled={save.isPending || blank}>{save.isPending ? t("settings.saving") : t("settings.save")}</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
