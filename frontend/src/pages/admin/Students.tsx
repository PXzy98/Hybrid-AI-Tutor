import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";

import { admin, type StudentAccount } from "../../api/endpoints";
import { useI18n, type T } from "../../i18n";

function fmt(t: T, locale: string, ts?: string | null) {
  return ts ? new Date(ts).toLocaleString(locale) : t("students.never");
}

/** A temporary password, shown once, with a copy button. */
export function OneTimePassword({ who, password, onClose }: { who: string; password: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  const { t } = useI18n();
  async function copy() {
    try {
      await navigator.clipboard.writeText(password);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }
  return (
    <div role="status" className="rounded-md border border-teal-200 bg-teal-50 p-4 text-sm">
      <p className="font-medium text-teal-900">{t("students.tempFor", { who })}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <code className="rounded bg-white px-2 py-1 text-base tracking-wide" data-testid="temp-password">{password}</code>
        <button type="button" className="btn-secondary py-1" onClick={copy}>{copied ? t("students.copied") : t("students.copy")}</button>
        <button type="button" className="btn-link" onClick={onClose}>{t("students.done")}</button>
      </div>
      <p className="mt-2 text-teal-900">
        {t("students.tempNote")}
      </p>
    </div>
  );
}

function DeleteDialog({ student, onCancel, onConfirm, busy }: {
  student: StudentAccount; onCancel: () => void; onConfirm: () => void; busy: boolean;
}) {
  const [typed, setTyped] = useState("");
  const { t } = useI18n();
  return (
    <div role="alertdialog" aria-labelledby="del-title" className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm">
      <p id="del-title" className="font-medium text-rose-900">{t("students.deleteTitle", { who: student.username })}</p>
      <p className="mt-1 text-rose-900">
        {t("students.deleteBody")}
      </p>
      <label className="label mt-3" htmlFor="del-confirm">{t("students.deleteType")}</label>
      <input id="del-confirm" className="input max-w-xs" value={typed} onChange={(e) => setTyped(e.target.value)}
             autoComplete="off" />
      <div className="mt-3 flex gap-2">
        <button type="button" className="btn bg-rose-700 text-white hover:bg-rose-800" onClick={onConfirm}
                disabled={typed.trim().toLowerCase() !== student.username || busy}>{t("students.deleteConfirm")}</button>
        <button type="button" className="btn-secondary" onClick={onCancel}>{t("students.cancel")}</button>
      </div>
    </div>
  );
}

/** Student-account management (design §7.5, §8.3): account data only, no learning data. */
export default function StudentsPage() {
  const qc = useQueryClient();
  const { t, locale } = useI18n();
  const students = useQuery({ queryKey: ["admin", "students"], queryFn: admin.students });
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [secret, setSecret] = useState<{ who: string; password: string } | null>(null);
  const [deleting, setDeleting] = useState<StudentAccount | null>(null);
  const [error, setError] = useState<string | null>(null);
  const refresh = () => qc.invalidateQueries({ queryKey: ["admin", "students"] });
  const fail = (e: Error) => setError(e.message);

  const create = useMutation({
    mutationFn: () => admin.createStudent(username.trim(), displayName.trim()),
    onSuccess: (r) => {
      setSecret({ who: r.account.username, password: r.temporary_password });
      setUsername("");
      setDisplayName("");
      setError(null);
      refresh();
    },
    onError: fail,
  });
  const reset = useMutation({
    mutationFn: (s: StudentAccount) => admin.resetPassword(s.id).then((r) => ({ s, r })),
    onSuccess: ({ s, r }) => {
      setSecret({ who: s.username, password: r.temporary_password });
      refresh();
    },
    onError: fail,
  });
  const toggle = useMutation({
    mutationFn: (s: StudentAccount) => admin.updateStudent(s.id, { active: !s.active }),
    onSuccess: refresh,
    onError: fail,
  });
  const remove = useMutation({
    mutationFn: (s: StudentAccount) => admin.deleteStudent(s.id),
    onSuccess: () => {
      setDeleting(null);
      refresh();
    },
    onError: fail,
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    if (username.trim()) create.mutate();
  }

  return (
    <div className="space-y-5">
      <form onSubmit={submit} className="card space-y-3" aria-labelledby="add-title">
        <h2 id="add-title" className="font-semibold">{t("students.addTitle")}</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="new-username">{t("students.username")}</label>
            <input id="new-username" className="input" value={username} onChange={(e) => setUsername(e.target.value)}
                   aria-describedby="username-hint" autoComplete="off" required minLength={3} maxLength={32} />
            <p id="username-hint" className="mt-1 text-xs text-slate-600">
              {t("students.usernameHint")}
            </p>
          </div>
          <div>
            <label className="label" htmlFor="new-display">{t("students.displayName")}</label>
            <input id="new-display" className="input" value={displayName} maxLength={80}
                   onChange={(e) => setDisplayName(e.target.value)} autoComplete="off" />
          </div>
        </div>
        <button type="submit" className="btn-primary" disabled={create.isPending}>{t("students.add")}</button>
      </form>

      {secret && <OneTimePassword who={secret.who} password={secret.password} onClose={() => setSecret(null)} />}
      {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
      {deleting && (
        <DeleteDialog student={deleting} busy={remove.isPending} onCancel={() => setDeleting(null)}
                      onConfirm={() => remove.mutate(deleting)} />
      )}

      <section className="card overflow-x-auto" aria-labelledby="list-title">
        <h2 id="list-title" className="mb-3 font-semibold">{t("students.list", { n: students.data?.length ?? 0 })}</h2>
        {students.isLoading && <p className="text-sm text-slate-600">{t("app.loading")}</p>}
        {students.data && students.data.length === 0 && <p className="text-sm text-slate-600">{t("students.none")}</p>}
        {students.data && students.data.length > 0 && (
          <table className="w-full text-left text-sm">
            <thead className="text-slate-600">
              <tr>
                <th className="py-2 pr-3 font-medium">{t("students.col.username")}</th>
                <th className="py-2 pr-3 font-medium">{t("students.col.name")}</th>
                <th className="py-2 pr-3 font-medium">{t("students.col.status")}</th>
                <th className="py-2 pr-3 font-medium">{t("students.col.created")}</th>
                <th className="py-2 pr-3 font-medium">{t("students.col.lastLogin")}</th>
                <th className="py-2 font-medium"><span className="sr-only">{t("students.col.actions")}</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {students.data.map((s) => (
                <tr key={s.id} className={s.active ? "" : "text-slate-500"}>
                  <td className="py-2 pr-3 font-mono">{s.username}</td>
                  <td className="py-2 pr-3">{s.display_name}</td>
                  <td className="py-2 pr-3">
                    {s.active ? t("students.active") : t("students.deactivated")}
                    {s.must_change_password && <span className="ml-1 text-xs text-amber-800">{t("students.pwPending")}</span>}
                  </td>
                  <td className="py-2 pr-3">{fmt(t, locale, s.created_at)}</td>
                  <td className="py-2 pr-3">{fmt(t, locale, s.last_login_at)}</td>
                  <td className="py-2">
                    <div className="flex flex-wrap justify-end gap-2">
                      <button type="button" className="btn-link" onClick={() => reset.mutate(s)}>{t("students.resetPw")}</button>
                      <button type="button" className="btn-link" onClick={() => toggle.mutate(s)}>
                        {s.active ? t("students.deactivate") : t("students.activate")}
                      </button>
                      <button type="button" className="btn-link text-rose-700" onClick={() => setDeleting(s)}>{t("students.delete")}</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
