import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useMe, useResetSession } from "@/auth";
import { ErrorNote } from "@/components/common";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useI18n } from "@/i18n";

const MIN_LENGTH = 10;

export default function ChangePassword() {
  const { data: me } = useMe();
  const navigate = useNavigate();
  const resetSession = useResetSession();
  const { t } = useI18n();
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
    <Card className="mx-auto max-w-md">
      <form onSubmit={submit} className="space-y-4">
        <CardHeader><CardTitle><h1 className="text-xl">{t("pw.title")}</h1></CardTitle></CardHeader>
        <CardContent className="space-y-4">
          {me?.must_change_password && <Alert variant="info">{t("pw.temporary")}</Alert>}
          <div className="grid gap-1.5">
            <Label htmlFor="pw-current">{t("pw.current")}</Label>
            <Input id="pw-current" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="pw-new">{t("pw.new")}</Label>
            <Input id="pw-new" type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} required />
            <p className="text-xs text-muted-foreground">{t("pw.hint", { n: MIN_LENGTH })}</p>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="pw-repeat">{t("pw.repeat")}</Label>
            <Input id="pw-repeat" type="password" autoComplete="new-password" value={repeat} onChange={(e) => setRepeat(e.target.value)} required />
          </div>
          {local && <Alert variant="destructive" role="alert">{local}</Alert>}
          <ErrorNote error={error} />
          <Button type="submit" disabled={busy}>{busy ? t("pw.saving") : t("pw.save")}</Button>
        </CardContent>
      </form>
    </Card>
  );
}
