import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { api } from "@/api/endpoints";
import { useMe, useResetSession } from "@/auth";
import { ErrorNote } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LanguageSwitch, useI18n } from "@/i18n";

/** Join a course with an invitation code. A logged-in student only needs the code; a new student also gives
 * an e-mail address, a display name and a password, which creates the account (api-v2.md 3.1). */
export default function Join() {
  const { data: me, isLoading } = useMe();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const resetSession = useResetSession();
  const { t } = useI18n();
  const [code, setCode] = useState(params.get("code") ?? "");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const out = await api.join(me ? { code: code.trim() } : { code: code.trim(), email, display_name: displayName, password });
      resetSession(out.me);
      navigate(`/courses/${out.course_id}`, { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  if (isLoading) return <p className="p-8 text-muted-foreground">{t("app.loading")}</p>;
  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-md">
        <form onSubmit={submit} className="space-y-4" aria-labelledby="join-title">
          <CardHeader>
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1.5">
                <h1 id="join-title" className="text-xl leading-none font-semibold">{t("join.title")}</h1>
                <CardDescription>{me ? t("join.introLoggedIn") : t("join.intro")}</CardDescription>
              </div>
              {!me && <LanguageSwitch />}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-1.5">
              <Label htmlFor="join-code">{t("join.code")}</Label>
              <Input id="join-code" aria-describedby={error ? "join-error" : undefined} aria-invalid={error ? true : undefined} value={code} onChange={(e) => setCode(e.target.value)} autoComplete="off" required />
            </div>
            {!me && (
              <>
                <div className="grid gap-1.5">
                  <Label htmlFor="join-email">{t("join.email")}</Label>
                  <Input id="join-email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="join-name">{t("join.name")}</Label>
                  <Input id="join-name" autoComplete="name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} required />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="join-password">{t("join.password")}</Label>
                  <Input id="join-password" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
                  <p className="text-xs text-muted-foreground">{t("pw.hint", { n: 10 })}</p>
                </div>
              </>
            )}
            <ErrorNote error={error} id="join-error" />
            <Button type="submit" className="w-full" disabled={busy}>{busy ? t("join.busy") : t("join.submit")}</Button>
            <p className="text-center text-sm text-muted-foreground">
              {me ? <Link to="/courses" className="text-primary underline">{t("join.back")}</Link>
                  : <>{t("join.haveAccount")} <Link to="/login" className="text-primary underline">{t("login.submit")}</Link></>}
            </p>
          </CardContent>
        </form>
      </Card>
    </main>
  );
}
