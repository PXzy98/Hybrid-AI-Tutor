import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useMe, useResetSession } from "@/auth";
import { ErrorNote } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LanguageSwitch, useI18n } from "@/i18n";

export default function Login() {
  const { data: me } = useMe();
  const navigate = useNavigate();
  const resetSession = useResetSession();
  const { t } = useI18n();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  if (me) return <Navigate to={me.must_change_password ? "/change-password" : "/courses"} replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const account = await api.login(username, password);
      resetSession(account);
      navigate(account.must_change_password ? "/change-password" : "/courses", { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm">
        <form onSubmit={submit} className="space-y-4" aria-labelledby="login-title">
          <CardHeader>
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1.5">
                <h1 id="login-title" className="text-xl leading-none font-semibold">{t("app.name")}</h1>
                <CardDescription>{t("login.intro")}</CardDescription>
              </div>
              <LanguageSwitch />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-1.5">
              <Label htmlFor="username">{t("login.username")}</Label>
              <Input id="username" aria-describedby={error ? "login-error" : undefined} autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="password">{t("login.password")}</Label>
              <Input id="password" aria-describedby={error ? "login-error" : undefined} aria-invalid={error ? true : undefined} type="password" autoComplete="current-password" value={password}
                     onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <ErrorNote error={error} id="login-error" />
            <Button type="submit" className="w-full" disabled={busy}>{busy ? t("login.busy") : t("login.submit")}</Button>
            <p className="text-center text-sm text-muted-foreground">
              {t("login.noAccount")} <Link to="/join" className="text-primary underline">{t("login.joinLink")}</Link>
            </p>
          </CardContent>
        </form>
      </Card>
    </main>
  );
}
