import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import { api, type Course, type Difficulty, type Module } from "@/api/endpoints";
import { ErrorNote } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useI18n } from "@/i18n";
import ContentTransfer from "./ContentTransfer";
import Misconceptions from "./Misconceptions";

const LEVELS: Difficulty[] = ["basic", "intermediate", "advanced"];
const CHOICES = ["A", "B", "C", "D"] as const;

/** Course management: modules, knowledge components (KCs), check items, misconceptions and YAML import/export. */
export default function Content({ course }: { course: Course }) {
  return (
    <div className="space-y-4">
      <ModulesCard course={course} />
      <KcsCard course={course} />
      <ItemsCard course={course} />
      <Misconceptions course={course} />
      <ContentTransfer course={course} />
    </div>
  );
}

function ModulesCard({ course }: { course: Course }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const modules = useQuery({ queryKey: ["modules", course.id], queryFn: () => api.modules(course.id) });
  const refresh = () => qc.invalidateQueries({ queryKey: ["modules", course.id] });
  const [form, setForm] = useState({ code: "", title: "", guideline: "" });
  const create = useMutation({
    mutationFn: () => api.createModule(course.id, form),
    onSuccess: () => { setForm({ code: "", title: "", guideline: "" }); refresh(); },
  });
  const remove = useMutation({ mutationFn: (id: number) => api.deleteModule(course.id, id), onSuccess: refresh });
  const reorder = useMutation({ mutationFn: (ids: number[]) => api.reorderModules(course.id, ids), onSuccess: refresh });
  const list = modules.data ?? [];
  const move = (i: number, d: -1 | 1) => {
    const ids = list.map((m) => m.id);
    [ids[i], ids[i + d]] = [ids[i + d], ids[i]];
    reorder.mutate(ids);
  };
  return (
    <Card>
      <CardHeader><CardTitle>{t("content.modules")}</CardTitle><CardDescription>{t("content.modulesHint")}</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        <ErrorNote error={modules.error ?? create.error ?? remove.error ?? reorder.error} />
        <ul className="space-y-3">
          {list.map((m, i) => (
            <li key={m.id} className="rounded-lg border p-3">
              <ModuleRow course={course} module={m} onSaved={refresh}
                         actions={<>
                           <Button type="button" size="icon" variant="ghost" aria-label={t("content.up", { name: m.title })} disabled={i === 0} onClick={() => move(i, -1)}><ArrowUp aria-hidden /></Button>
                           <Button type="button" size="icon" variant="ghost" aria-label={t("content.down", { name: m.title })} disabled={i === list.length - 1} onClick={() => move(i, 1)}><ArrowDown aria-hidden /></Button>
                           <Button type="button" size="icon" variant="ghost" aria-label={t("content.deleteModule", { name: m.title })} onClick={() => remove.mutate(m.id)}><Trash2 aria-hidden /></Button>
                         </>} />
            </li>
          ))}
          {modules.data && list.length === 0 && <li className="text-sm text-muted-foreground">{t("nav.noModules")}</li>}
        </ul>
        <form className="grid gap-3 border-t pt-4 sm:grid-cols-[1fr_2fr]" onSubmit={(e: FormEvent) => { e.preventDefault(); create.mutate(); }} aria-label={t("content.addModule")}>
          <div className="grid gap-1.5"><Label htmlFor="mod-code">{t("content.moduleCode")}</Label>
            <Input id="mod-code" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required /></div>
          <div className="grid gap-1.5"><Label htmlFor="mod-title">{t("course.title")}</Label>
            <Input id="mod-title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required /></div>
          <div className="grid gap-1.5 sm:col-span-2"><Label htmlFor="mod-guideline">{t("content.guideline")}</Label>
            <Textarea id="mod-guideline" value={form.guideline} onChange={(e) => setForm({ ...form, guideline: e.target.value })} /></div>
          <div className="sm:col-span-2"><Button type="submit" disabled={create.isPending}>{t("content.addModule")}</Button></div>
        </form>
      </CardContent>
    </Card>
  );
}

function ModuleRow({ course, module, onSaved, actions }: { course: Course; module: Module; onSaved: () => void; actions: React.ReactNode }) {
  const { t } = useI18n();
  const [title, setTitle] = useState(module.title);
  const [guideline, setGuideline] = useState(module.guideline ?? "");
  const save = useMutation({ mutationFn: () => api.updateModule(course.id, module.id, { title, guideline }), onSuccess: onSaved });
  const changed = title !== module.title || guideline !== (module.guideline ?? "");
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Badge variant="outline">{module.code}</Badge>
        <Input aria-label={t("content.titleOf", { name: module.title })} value={title} onChange={(e) => setTitle(e.target.value)} />
        <div className="flex shrink-0">{actions}</div>
      </div>
      <Textarea aria-label={t("content.guidelineOf", { name: module.title })} value={guideline} onChange={(e) => setGuideline(e.target.value)} />
      <ErrorNote error={save.error} />
      {changed && <Button type="button" size="sm" onClick={() => save.mutate()} disabled={save.isPending}>{t("settings.save")}</Button>}
    </div>
  );
}

function KcsCard({ course }: { course: Course }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const modules = useQuery({ queryKey: ["modules", course.id], queryFn: () => api.modules(course.id) });
  const kcs = useQuery({ queryKey: ["kcs", course.id], queryFn: () => api.kcs(course.id) });
  const refresh = () => qc.invalidateQueries({ queryKey: ["kcs", course.id] });
  const [form, setForm] = useState({ module_id: 0, code: "", name: "", definition: "", difficulty: "basic" as Difficulty });
  const moduleId = form.module_id || modules.data?.[0]?.id || 0;
  const create = useMutation({
    mutationFn: () => api.createKc(course.id, { ...form, module_id: moduleId }),
    onSuccess: () => { setForm({ ...form, code: "", name: "", definition: "" }); refresh(); },
  });
  const retire = useMutation({ mutationFn: (id: number) => api.updateKc(course.id, id, { status: "retired" }), onSuccess: refresh });
  return (
    <Card>
      <CardHeader><CardTitle>{t("content.kcs")}</CardTitle><CardDescription>{t("content.kcsHint")}</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        <ErrorNote error={kcs.error ?? create.error ?? retire.error} />
        <ul className="divide-y text-sm">
          {kcs.data?.map((k) => (
            <li key={k.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span><span className="font-medium">{k.code}</span> {k.name} <Badge variant="outline">{t(`band.${k.difficulty}`)}</Badge>{" "}
                <Badge variant={k.status === "active" ? "success" : "secondary"}>{t(`content.status.${k.status}`)}</Badge></span>
              {k.status !== "retired" && <Button type="button" size="sm" variant="outline" aria-label={t("content.retireFor", { name: k.name })} onClick={() => retire.mutate(k.id)}>{t("content.retire")}</Button>}
            </li>
          ))}
          {kcs.data?.length === 0 && <li className="py-2 text-muted-foreground">{t("content.noKcs")}</li>}
        </ul>
        <form className="grid gap-3 border-t pt-4 sm:grid-cols-2" onSubmit={(e: FormEvent) => { e.preventDefault(); create.mutate(); }} aria-label={t("content.addKc")}>
          <div className="grid gap-1.5"><Label htmlFor="kc-module">{t("content.module")}</Label>
            <Select id="kc-module" value={moduleId} onChange={(e) => setForm({ ...form, module_id: Number(e.target.value) })}>
              {modules.data?.map((m) => <option key={m.id} value={m.id}>{m.title}</option>)}
            </Select></div>
          <div className="grid gap-1.5"><Label htmlFor="kc-level">{t("content.level")}</Label>
            <Select id="kc-level" value={form.difficulty} onChange={(e) => setForm({ ...form, difficulty: e.target.value as Difficulty })}>
              {LEVELS.map((l) => <option key={l} value={l}>{t(`band.${l}`)}</option>)}
            </Select></div>
          <div className="grid gap-1.5"><Label htmlFor="kc-code">{t("content.kcCode")}</Label>
            <Input id="kc-code" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required /></div>
          <div className="grid gap-1.5"><Label htmlFor="kc-name">{t("content.kcName")}</Label>
            <Input id="kc-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></div>
          <div className="grid gap-1.5 sm:col-span-2"><Label htmlFor="kc-def">{t("content.definition")}</Label>
            <Textarea id="kc-def" value={form.definition} onChange={(e) => setForm({ ...form, definition: e.target.value })} /></div>
          <div className="sm:col-span-2"><Button type="submit" disabled={create.isPending || !moduleId}>{t("content.addKc")}</Button></div>
        </form>
      </CardContent>
    </Card>
  );
}

function ItemsCard({ course }: { course: Course }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const kcs = useQuery({ queryKey: ["kcs", course.id], queryFn: () => api.kcs(course.id) });
  const items = useQuery({ queryKey: ["check-items", course.id], queryFn: () => api.checkItems(course.id) });
  const refresh = () => qc.invalidateQueries({ queryKey: ["check-items", course.id] });
  const blank = { kc_id: 0, code: "", level: "basic" as Difficulty, stem: "", answer: "A" as (typeof CHOICES)[number], explanation: "", options: { A: "", B: "", C: "", D: "" } };
  const [form, setForm] = useState(blank);
  const kcId = form.kc_id || kcs.data?.[0]?.id || 0;
  const create = useMutation({
    mutationFn: () => api.createCheckItem(course.id, {
      kc_id: kcId, code: form.code, level: form.level, stem: form.stem, answer: form.answer, explanation: form.explanation,
      options: Object.fromEntries(CHOICES.map((c) => [c, { text: form.options[c] }])),
    }),
    onSuccess: () => { setForm({ ...blank, kc_id: kcId }); refresh(); },
  });
  const retire = useMutation({ mutationFn: (id: number) => api.updateCheckItem(course.id, id, { status: "retired" }), onSuccess: refresh });
  return (
    <Card>
      <CardHeader><CardTitle>{t("content.items")}</CardTitle><CardDescription>{t("content.itemsHint")}</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        <ErrorNote error={items.error ?? create.error ?? retire.error} />
        <ul className="divide-y text-sm">
          {items.data?.map((it) => (
            <li key={it.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span><span className="font-medium">{it.code}</span> {it.stem}{" "}
                <Badge variant={it.status === "active" ? "success" : "secondary"}>{t(`content.status.${it.status}`)}</Badge></span>
              {it.status !== "retired" && <Button type="button" size="sm" variant="outline" aria-label={t("content.retireFor", { name: it.code })} onClick={() => retire.mutate(it.id)}>{t("content.retire")}</Button>}
            </li>
          ))}
          {items.data?.length === 0 && <li className="py-2 text-muted-foreground">{t("content.noItems")}</li>}
        </ul>
        <form className="grid gap-3 border-t pt-4 sm:grid-cols-2" onSubmit={(e: FormEvent) => { e.preventDefault(); create.mutate(); }} aria-label={t("content.addItem")}>
          <div className="grid gap-1.5"><Label htmlFor="it-kc">{t("content.kc")}</Label>
            <Select id="it-kc" value={kcId} onChange={(e) => setForm({ ...form, kc_id: Number(e.target.value) })}>
              {kcs.data?.map((k) => <option key={k.id} value={k.id}>{k.code} {k.name}</option>)}
            </Select></div>
          <div className="grid gap-1.5"><Label htmlFor="it-code">{t("content.itemCode")}</Label>
            <Input id="it-code" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required /></div>
          <div className="grid gap-1.5 sm:col-span-2"><Label htmlFor="it-stem">{t("content.stem")}</Label>
            <Textarea id="it-stem" value={form.stem} onChange={(e) => setForm({ ...form, stem: e.target.value })} required /></div>
          {CHOICES.map((c) => (
            <div key={c} className="grid gap-1.5"><Label htmlFor={`it-opt-${c}`}>{t("content.option", { key: c })}</Label>
              <Input id={`it-opt-${c}`} value={form.options[c]} onChange={(e) => setForm({ ...form, options: { ...form.options, [c]: e.target.value } })} required /></div>
          ))}
          <div className="grid gap-1.5"><Label htmlFor="it-answer">{t("content.answer")}</Label>
            <Select id="it-answer" value={form.answer} onChange={(e) => setForm({ ...form, answer: e.target.value as (typeof CHOICES)[number] })}>
              {CHOICES.map((c) => <option key={c} value={c}>{c}</option>)}
            </Select></div>
          <div className="grid gap-1.5"><Label htmlFor="it-level">{t("content.level")}</Label>
            <Select id="it-level" value={form.level} onChange={(e) => setForm({ ...form, level: e.target.value as Difficulty })}>
              {LEVELS.map((l) => <option key={l} value={l}>{t(`band.${l}`)}</option>)}
            </Select></div>
          <div className="grid gap-1.5 sm:col-span-2"><Label htmlFor="it-expl">{t("content.explanation")}</Label>
            <Textarea id="it-expl" value={form.explanation} onChange={(e) => setForm({ ...form, explanation: e.target.value })} /></div>
          <div className="sm:col-span-2"><Button type="submit" disabled={create.isPending || !kcId}>{t("content.addItem")}</Button></div>
        </form>
      </CardContent>
    </Card>
  );
}
