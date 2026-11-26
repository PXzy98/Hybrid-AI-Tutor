import { Eye, EyeOff } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useMe, useResetSession } from "@/auth";
import AuthLayout from "@/components/AuthLayout";
import { ErrorNote, REQUIRED_LABEL } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useI18n } from "@/i18n";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

export default function Login() {
  const { data: me } = useMe();
  const navigate = useNavigate();
  const resetSession = useResetSession();
  const { t } = useI18n();
  useDocumentTitle(t("login.submit"));
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [shown, setShown] = useState(false);

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
    <AuthLayout title={t("app.name")} titleId="login-title"
                below={<p className="px-2 text-center text-xs leading-relaxed text-muted-foreground">{t("login.intro")}</p>}>
      <form onSubmit={submit} className="space-y-4" aria-labelledby="login-title">
        <div className="grid gap-1.5">
          <Label htmlFor="username" className={REQUIRED_LABEL}>{t("login.username")}</Label>
          <Input id="username" className="h-10" aria-describedby={error ? "login-error" : undefined} autoComplete="username" autoCapitalize="off" autoCorrect="off" spellCheck={false} value={username} onChange={(e) => setUsername(e.target.value)} required aria-required />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="password" className={REQUIRED_LABEL}>{t("login.password")}</Label>
          <div className="relative">
            <Input id="password" className="h-10 pr-10" aria-describedby={error ? "login-error" : undefined} aria-invalid={error ? true : undefined} type={shown ? "text" : "password"} autoComplete="current-password" value={password}
                   onChange={(e) => setPassword(e.target.value)} required aria-required />
            <Button type="button" variant="ghost" size="icon-sm" className="absolute top-1/2 right-1 -translate-y-1/2 text-muted-foreground"
                    aria-label={t("login.showPassword")} aria-pressed={shown} onClick={() => setShown(!shown)}>
              {shown ? <EyeOff aria-hidden /> : <Eye aria-hidden />}
            </Button>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">{t("login.required")}</p>
        <ErrorNote error={error} id="login-error" />
        <Button type="submit" size="lg" className="w-full" loading={busy}>{busy ? t("login.busy") : t("login.submit")}</Button>
        <p className="text-center text-sm text-muted-foreground">
          {t("login.noAccount")} <Link to="/join" className="font-medium text-primary underline-offset-4 hover:underline">{t("login.joinLink")}</Link>
        </p>
      </form>
    </AuthLayout>
  );
}
