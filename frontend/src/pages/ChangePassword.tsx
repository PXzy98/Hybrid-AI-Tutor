import { KeyRound } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useMe, useResetSession } from "@/auth";
import { ErrorNote } from "@/components/common";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useI18n } from "@/i18n";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

const MIN_LENGTH = 10;

export default function ChangePassword() {
  const { data: me } = useMe();
  const navigate = useNavigate();
  const resetSession = useResetSession();
  const { t } = useI18n();
  useDocumentTitle(t("pw.title"));
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [local, setLocal] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLocal("");
    if (next !== repeat) return setLocal(t("pw.mismatch"));
    if (next.length < MIN_LENGTH) return setLocal(t("pw.tooShort", { n: MIN_LENGTH }));
    setBusy(true);
    try {
      const account = await api.changePassword(current, next);
      resetSession(account);
      navigate("/courses", { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-sm space-y-6 py-6">
      <div className="flex flex-col items-center gap-3 text-center">
        <span aria-hidden className="flex size-10 items-center justify-center rounded-full bg-muted text-muted-foreground"><KeyRound className="size-5" /></span>
        <h1 className="text-xl font-semibold tracking-tight">{t("pw.title")}</h1>
      </div>
      <form onSubmit={submit} className="space-y-4 rounded-xl border bg-card p-6">
        {me?.must_change_password && <Alert variant="info" icon>{t("pw.temporary")}</Alert>}
        <div className="grid gap-1.5">
          <Label htmlFor="pw-current">{t("pw.current")}</Label>
          <Input id="pw-current" className="h-10" aria-describedby={error ? "pw-error" : undefined} type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="pw-new">{t("pw.new")}</Label>
          <Input id="pw-new" className="h-10" aria-describedby={local ? "pw-local" : "pw-hint"} aria-invalid={local ? true : undefined} type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} required />
          <p id="pw-hint" className="text-xs text-muted-foreground">{t("pw.hint", { n: MIN_LENGTH })}</p>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="pw-repeat">{t("pw.repeat")}</Label>
          <Input id="pw-repeat" className="h-10" type="password" autoComplete="new-password" value={repeat} onChange={(e) => setRepeat(e.target.value)} required />
        </div>
        {local && <Alert variant="destructive" role="alert" id="pw-local" icon>{local}</Alert>}
        <ErrorNote error={error} id="pw-error" />
        <Button type="submit" size="lg" className="w-full" loading={busy}>{busy ? t("pw.saving") : t("pw.save")}</Button>
      </form>
    </div>
  );
}
