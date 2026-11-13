import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, RefreshCw } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";

import { api, type Course, type ImportReport } from "@/api/endpoints";
import { ErrorNote } from "@/components/common";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useI18n } from "@/i18n";

/** Members: invitation code, CSV import, co-instructors and the member list. */
export default function Members({ course }: { course: Course }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const members = useQuery({ queryKey: ["members", course.id], queryFn: () => api.members(course.id) });
  const refresh = () => qc.invalidateQueries({ queryKey: ["members", course.id] });
  const [temporary, setTemporary] = useState<{ name: string; password: string } | null>(null);
  const remove = useMutation({ mutationFn: (id: number) => api.removeMember(course.id, id), onSuccess: refresh });
  const reset = useMutation({
    mutationFn: async (m: { id: number; name: string }) => ({ name: m.name, password: (await api.resetMemberPassword(course.id, m.id)).temporary_password }),
    onSuccess: setTemporary,
  });
  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <InviteCard course={course} />
        <ImportCard course={course} onDone={refresh} />
      </div>
      <AddInstructor course={course} onDone={refresh} />
      {temporary && (
        <Alert variant="warning" role="status">
          {t("members.temporary", { name: temporary.name })} <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-foreground">{temporary.password}</code>
          <p className="mt-1 text-xs">{t("members.temporaryHint")}</p>
        </Alert>
      )}
      <ErrorNote error={members.error ?? remove.error ?? reset.error} />
      <Card>
        <CardHeader><CardTitle>{t("members.title", { n: members.data?.length ?? 0 })}</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader><TableRow>
              <TableHead>{t("members.name")}</TableHead><TableHead>{t("members.email")}</TableHead>
              <TableHead>{t("members.role")}</TableHead><TableHead>{t("members.status")}</TableHead>
              <TableHead><span className="sr-only">{t("students.actions")}</span></TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {members.data?.map((m) => (
                <TableRow key={m.id}>
                  <TableCell className="font-medium">{m.display_name ?? m.username ?? "—"}</TableCell>
                  <TableCell>{m.email ?? "—"}</TableCell>
                  <TableCell>{t(`role.${m.role}`)}</TableCell>
                  <TableCell><Badge variant={m.status === "active" ? "success" : "secondary"}>{t(`members.status.${m.status}`)}</Badge></TableCell>
                  <TableCell className="space-x-2 text-right whitespace-nowrap">
                    {m.role === "student" && m.status === "active" && (
                      <Button type="button" size="sm" variant="outline" onClick={() => reset.mutate({ id: m.id, name: m.display_name ?? "" })}>{t("members.reset")}</Button>
                    )}
                    <Button type="button" size="sm" variant="outline" aria-label={t("members.removeFor", { name: m.display_name ?? m.email ?? "" })}
                            onClick={() => remove.mutate(m.id)}>{t("members.remove")}</Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function InviteCard({ course }: { course: Course }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const invite = useQuery({ queryKey: ["invite", course.id], queryFn: () => api.invite(course.id) });
  const rotate = useMutation({
    mutationFn: () => api.rotateInvite(course.id),
    onSuccess: (fresh) => qc.setQueryData(["invite", course.id], fresh),
  });
  const data = invite.data;
  const code = data?.code;
  return (
    <Card>
      <CardHeader><CardTitle>{t("invite.title")}</CardTitle><CardDescription>{t("invite.hint")}</CardDescription></CardHeader>
      <CardContent className="space-y-3 text-sm">
        <ErrorNote error={invite.error ?? rotate.error} />
        {code ? (
          <div className="flex items-center gap-2">
            <code aria-label={t("invite.code")} className="rounded bg-muted px-2 py-1 font-mono text-base">{code}</code>
            <Button type="button" variant="ghost" size="icon" aria-label={t("invite.copy")}
                    onClick={() => navigator.clipboard?.writeText(code).catch(() => undefined)}><Copy aria-hidden /></Button>
          </div>
        ) : <p className="text-muted-foreground">{data ? t("invite.notShown") : t("invite.none")}</p>}
        {data && (
          <p className="text-muted-foreground">
            {t("invite.uses", { n: data.uses, max: data.max_uses ?? "∞" })}
            {data.expires_at && ` · ${t(data.expired ? "invite.expired" : "invite.expires", { date: new Date(data.expires_at).toLocaleDateString() })}`}
          </p>
        )}
        <Button type="button" variant="outline" onClick={() => rotate.mutate()} disabled={rotate.isPending}>
          <RefreshCw aria-hidden />{t("invite.rotate")}
        </Button>
      </CardContent>
    </Card>
  );
}

function ImportCard({ course, onDone }: { course: Course; onDone: () => void }) {
  const { t } = useI18n();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const run = useMutation({
    mutationFn: (f: File) => api.importMembers(course.id, f),
    onSuccess: (r) => { setReport(r); onDone(); if (input.current) input.current.value = ""; setFile(null); },
  });
  function submit(e: FormEvent) {
    e.preventDefault();
    if (file) run.mutate(file);
  }
  return (
    <Card>
      <CardHeader><CardTitle>{t("import.title")}</CardTitle><CardDescription>{t("import.hint")}</CardDescription></CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-3">
          <div className="grid gap-1.5">
            <Label htmlFor="import-file">{t("import.file")}</Label>
            <Input id="import-file" ref={input} type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </div>
          <ErrorNote error={run.error} />
          <Button type="submit" disabled={!file || run.isPending}>{run.isPending ? t("import.busy") : t("import.submit")}</Button>
        </form>
        {report && (
          <div role="status" className="mt-4 space-y-1 text-sm">
            <p className="font-medium">{t("import.report")}</p>
            <ul className="list-disc pl-5">
              <li>{t("import.added", { n: report.added.length })}</li>
              <li>{t("import.pending", { n: report.pending.length })}</li>
              <li>{t("import.unchanged", { n: report.unchanged.length })}</li>
              <li>{t("import.rejected", { n: report.rejected.length })}</li>
            </ul>
            {report.rejected.length > 0 && (
              <ul className="text-destructive">
                {report.rejected.map((r) => <li key={r.row}>{t("import.row", { n: r.row })}: {r.email || "—"} — {r.reason}</li>)}
              </ul>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function AddInstructor({ course, onDone }: { course: Course; onDone: () => void }) {
  const { t } = useI18n();
  const [email, setEmail] = useState("");
  const add = useMutation({ mutationFn: () => api.addInstructor(course.id, email), onSuccess: () => { setEmail(""); onDone(); } });
  return (
    <Card>
      <CardHeader><CardTitle>{t("coinstructor.title")}</CardTitle><CardDescription>{t("coinstructor.hint")}</CardDescription></CardHeader>
      <CardContent>
        <form className="flex flex-wrap items-end gap-3" onSubmit={(e) => { e.preventDefault(); add.mutate(); }}>
          <div className="grid gap-1.5">
            <Label htmlFor="coinstructor-email">{t("members.email")}</Label>
            <Input id="coinstructor-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <Button type="submit" disabled={add.isPending}>{t("coinstructor.add")}</Button>
        </form>
        <div className="mt-3"><ErrorNote error={add.error} /></div>
      </CardContent>
    </Card>
  );
}
