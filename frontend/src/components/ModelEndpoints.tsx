import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import { api, type ModelEndpoint } from "@/api/endpoints";
import { ErrorNote } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useI18n } from "@/i18n";

export const endpointsKey = (courseId: number | null) => ["model-endpoints", courseId] as const;

/** Model connections of the system (courseId null, administrators) or of one course (instructors). The stored API
 * key is never sent to the browser: only whether one is set and its last four characters. */
export default function ModelEndpoints({ courseId }: { courseId: number | null }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const list = useQuery({ queryKey: endpointsKey(courseId), queryFn: () => api.modelEndpoints(courseId) });
  const remove = useMutation({
    mutationFn: (id: number) => api.deleteModelEndpoint(courseId, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: endpointsKey(courseId) }),
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("models.title")}</CardTitle>
        <CardDescription>{t(courseId === null ? "models.hintSystem" : "models.hintCourse")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <ErrorNote error={list.error ?? remove.error} />
        {list.data?.length === 0 && <p className="text-sm text-muted-foreground">{t("models.none")}</p>}
        {!!list.data?.length && (
          <Table>
            <TableHeader><TableRow>
              <TableHead>{t("models.name")}</TableHead><TableHead>{t("models.model")}</TableHead>
              <TableHead>{t("models.trust")}</TableHead><TableHead>{t("models.key")}</TableHead>
              <TableHead><span className="sr-only">{t("students.actions")}</span></TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {list.data.map((e) => (
                <TableRow key={e.id}>
                  <TableCell className="font-medium">{e.name}<br /><span className="text-xs font-normal text-muted-foreground">{e.base_url}</span></TableCell>
                  <TableCell>{e.model} <span className="text-xs text-muted-foreground">({t(`models.kind.${e.kind}`)})</span></TableCell>
                  <TableCell>
                    <Badge variant={e.trust === "trusted_local" ? "success" : "warning"}>{t(`models.trust.${e.trust}`)}</Badge>
                  </TableCell>
                  <TableCell>{e.api_key_last4 ? t("models.keySet", { last4: e.api_key_last4 }) : t("models.keyNone")}</TableCell>
                  <TableCell className="space-x-1 text-right">
                    <EndpointDialog courseId={courseId} endpoint={e} />
                    <Button type="button" size="sm" variant="outline" aria-label={t("models.deleteFor", { name: e.name })}
                            onClick={() => remove.mutate(e.id)}><Trash2 aria-hidden />{t("models.delete")}</Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        <EndpointDialog courseId={courseId} />
      </CardContent>
    </Card>
  );
}

/** Create (no endpoint) or edit one connection. The key field starts empty; leaving it empty keeps the stored key. */
function EndpointDialog({ courseId, endpoint }: { courseId: number | null; endpoint?: ModelEndpoint }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const blank = { name: "", kind: "ollama" as ModelEndpoint["kind"], base_url: "", model: "", trust: "external" as ModelEndpoint["trust"], api_key: "", confirm_controlled: false };
  const initial = endpoint ? { ...blank, name: endpoint.name, kind: endpoint.kind, base_url: endpoint.base_url, model: endpoint.model, trust: endpoint.trust } : blank;
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(initial);
  const save = useMutation({
    mutationFn: () => {
      const { api_key, ...rest } = form;
      const body = { ...rest, ...(api_key ? { api_key } : {}) };
      return endpoint ? api.updateModelEndpoint(courseId, endpoint.id, body) : api.createModelEndpoint(courseId, body);
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: endpointsKey(courseId) });
      setOpen(false);
      setForm(initial);
    },
  });
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });
  const p = endpoint ? `me-${endpoint.id}` : "me-new";
  function submit(e: FormEvent) {
    e.preventDefault();
    save.mutate();
  }
  return (
    <Dialog open={open} onOpenChange={(next) => { setOpen(next); if (next) { setForm(initial); save.reset(); } }}>
      <DialogTrigger asChild>
        {endpoint
          ? <Button type="button" size="sm" variant="outline" aria-label={t("models.editFor", { name: endpoint.name })}><Pencil aria-hidden />{t("models.edit")}</Button>
          : <Button type="button"><Plus aria-hidden />{t("models.add")}</Button>}
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={submit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>{t(endpoint ? "models.editTitle" : "models.add")}</DialogTitle>
            <DialogDescription>{t("models.formHint")}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5"><Label htmlFor={`${p}-name`}>{t("models.name")}</Label>
            <Input id={`${p}-name`} value={form.name} onChange={set("name")} required maxLength={100} /></div>
          <div className="grid gap-1.5"><Label htmlFor={`${p}-kind`}>{t("models.kindLabel")}</Label>
            <Select id={`${p}-kind`} value={form.kind} onChange={set("kind")}>
              <option value="ollama">{t("models.kind.ollama")}</option>
              <option value="openai_compat">{t("models.kind.openai_compat")}</option>
            </Select></div>
          <div className="grid gap-1.5"><Label htmlFor={`${p}-url`}>{t("models.url")}</Label>
            <Input id={`${p}-url`} type="url" value={form.base_url} onChange={set("base_url")} required maxLength={300} /></div>
          <div className="grid gap-1.5"><Label htmlFor={`${p}-model`}>{t("models.model")}</Label>
            <Input id={`${p}-model`} value={form.model} onChange={set("model")} required maxLength={100} /></div>
          <div className="grid gap-1.5"><Label htmlFor={`${p}-trust`}>{t("models.trust")}</Label>
            <Select id={`${p}-trust`} value={form.trust} onChange={set("trust")}>
              <option value="external">{t("models.trust.external")}</option>
              <option value="trusted_local">{t("models.trust.trusted_local")}</option>
            </Select>
            <p className="text-xs text-muted-foreground">{t(form.trust === "trusted_local" ? "models.trustLocalHint" : "models.trustExternalHint")}</p></div>
          {form.trust === "trusted_local" && (
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" className="mt-0.5 accent-primary" checked={form.confirm_controlled}
                     onChange={(e) => setForm({ ...form, confirm_controlled: e.target.checked })} />
              <span>{t("models.confirmControlled")}</span>
            </label>
          )}
          <div className="grid gap-1.5"><Label htmlFor={`${p}-key`}>{t("models.apiKey")}</Label>
            <Input id={`${p}-key`} type="password" autoComplete="off" value={form.api_key} onChange={set("api_key")} maxLength={500} />
            <p className="text-xs text-muted-foreground">{t(endpoint ? "models.keyKeep" : "models.keyOptional")}</p></div>
          <ErrorNote error={save.error} />
          <DialogFooter><Button type="submit" disabled={save.isPending}>{save.isPending ? t("settings.saving") : t("settings.save")}</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
