import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { api } from "../api/endpoints";
import { homeFor, useMe, useResetSession } from "../auth";
import { useI18n } from "../i18n";

const MIN_LENGTH = 10;

export default function ChangePassword() {
  const { data: me } = useMe();
  const navigate = useNavigate();
  const resetSession = useResetSession();
  const { t } = useI18n();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (next !== repeat) return setError(t("pw.mismatch"));
    if (next.length < MIN_LENGTH) return setError(t("pw.tooShort", { n: MIN_LENGTH }));
    setBusy(true);
    try {
      const account = await api.changePassword(current, next);
      resetSession(account);
      navigate(homeFor(account) === "/chat" ? "/start" : homeFor(account), { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("app.serverUnreachable"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="card mx-auto max-w-md space-y-4" aria-labelledby="pw-title">
      <div>
        <h1 id="pw-title" className="text-lg font-semibold">{t("pw.title")}</h1>
        {me?.must_change_password && (
          <p className="text-sm text-slate-600">
            {t("pw.temporary")}
          </p>
        )}
      </div>
      <div>
        <label htmlFor="current" className="label">{t("pw.current")}</label>
        <input id="current" type="password" className="input" autoComplete="current-password" value={current}
               onChange={(e) => setCurrent(e.target.value)} required />
      </div>
      <div>
        <label htmlFor="new" className="label">{t("pw.new")}</label>
        <input id="new" type="password" className="input" autoComplete="new-password" value={next}
               aria-describedby="pw-hint" onChange={(e) => setNext(e.target.value)} required />
        <p id="pw-hint" className="mt-1 text-xs text-slate-500">{t("pw.hint", { n: MIN_LENGTH })}</p>
      </div>
      <div>
        <label htmlFor="repeat" className="label">{t("pw.repeat")}</label>
        <input id="repeat" type="password" className="input" autoComplete="new-password" value={repeat}
               onChange={(e) => setRepeat(e.target.value)} required />
      </div>
      {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
      <button type="submit" className="btn-primary" disabled={busy}>{busy ? t("pw.saving") : t("pw.save")}</button>
    </form>
  );
}
