import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { api } from "../api/endpoints";
import { homeFor, useMe, useResetSession } from "../auth";
import { LanguageSwitch, useI18n } from "../i18n";

export default function Login() {
  const { data: me } = useMe();
  const navigate = useNavigate();
  const resetSession = useResetSession();
  const { t } = useI18n();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (me) return <Navigate to={homeFor(me)} replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const account = await api.login(username, password);
      resetSession(account);
      navigate(homeFor(account), { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("app.serverUnreachable"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <form onSubmit={submit} className="card w-full max-w-sm space-y-4" aria-labelledby="login-title">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 id="login-title" className="text-xl font-semibold text-slate-900">{t("app.name")}</h1>
            <p className="text-sm text-slate-600">{t("login.intro")}</p>
          </div>
          <LanguageSwitch />
        </div>
        <div>
          <label htmlFor="username" className="label">{t("login.username")}</label>
          <input id="username" className="input" autoComplete="username" value={username}
                 onChange={(e) => setUsername(e.target.value)} required />
        </div>
        <div>
          <label htmlFor="password" className="label">{t("login.password")}</label>
          <input id="password" type="password" className="input" autoComplete="current-password" value={password}
                 onChange={(e) => setPassword(e.target.value)} required />
        </div>
        {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
        <button type="submit" className="btn-primary w-full" disabled={busy}>{busy ? t("login.busy") : t("login.submit")}</button>
      </form>
    </main>
  );
}
