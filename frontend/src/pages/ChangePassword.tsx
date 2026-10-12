import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { api } from "../api/endpoints";
import { homeFor, useMe, useResetSession } from "../auth";

const MIN_LENGTH = 10;

export default function ChangePassword() {
  const { data: me } = useMe();
  const navigate = useNavigate();
  const resetSession = useResetSession();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (next !== repeat) return setError("The new passwords do not match.");
    if (next.length < MIN_LENGTH) return setError(`Use at least ${MIN_LENGTH} characters.`);
    setBusy(true);
    try {
      const account = await api.changePassword(current, next);
      resetSession(account);
      navigate(homeFor(account) === "/chat" ? "/start" : homeFor(account), { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The server is not reachable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="card mx-auto max-w-md space-y-4" aria-labelledby="pw-title">
      <div>
        <h1 id="pw-title" className="text-lg font-semibold">Choose your password</h1>
        {me?.must_change_password && (
          <p className="text-sm text-slate-600">
            You logged in with a temporary password. Please choose your own before you continue.
          </p>
        )}
      </div>
      <div>
        <label htmlFor="current" className="label">Current (temporary) password</label>
        <input id="current" type="password" className="input" autoComplete="current-password" value={current}
               onChange={(e) => setCurrent(e.target.value)} required />
      </div>
      <div>
        <label htmlFor="new" className="label">New password</label>
        <input id="new" type="password" className="input" autoComplete="new-password" value={next}
               aria-describedby="pw-hint" onChange={(e) => setNext(e.target.value)} required />
        <p id="pw-hint" className="mt-1 text-xs text-slate-500">At least {MIN_LENGTH} characters.</p>
      </div>
      <div>
        <label htmlFor="repeat" className="label">Repeat the new password</label>
        <input id="repeat" type="password" className="input" autoComplete="new-password" value={repeat}
               onChange={(e) => setRepeat(e.target.value)} required />
      </div>
      {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
      <button type="submit" className="btn-primary" disabled={busy}>{busy ? "Saving…" : "Save password"}</button>
    </form>
  );
}
