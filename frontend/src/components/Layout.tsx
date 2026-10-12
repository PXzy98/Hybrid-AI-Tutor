import type { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";

import { api, type Me } from "../api/endpoints";
import { useResetSession } from "../auth";
import ErrorBoundary from "./ErrorBoundary";

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded px-3 py-1.5 text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 ${
    isActive ? "bg-teal-50 text-teal-900" : "text-slate-700 hover:bg-slate-100"
  }`;

export default function Layout({ me, children }: { me: Me; children: ReactNode }) {
  const navigate = useNavigate();
  const resetSession = useResetSession();

  async function logout() {
    await api.logout().catch(() => undefined);
    resetSession(null);
    navigate("/login", { replace: true });
  }

  const student = me.role === "student" && !me.must_change_password;
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-2 px-4 py-3">
          <span className="mr-4 font-semibold text-teal-800">Health Tutor</span>
          {student && (
            <nav aria-label="Main" className="flex gap-1">
              <NavLink to="/chat" className={navClass}>Chat</NavLink>
              <NavLink to="/me" className={navClass}>What I know</NavLink>
              <NavLink to="/start" className={navClass}>Personalize</NavLink>
            </nav>
          )}
          <div className="ml-auto flex items-center gap-3 text-sm text-slate-600">
            <span>{me.display_name}</span>
            <button type="button" className="btn-secondary py-1.5" onClick={logout}>Log out</button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6">
        <ErrorBoundary>{children}</ErrorBoundary>
      </main>
      <footer role="note" className="border-t border-amber-200 bg-amber-50 py-2 text-center text-sm text-amber-900">
        For learning only — not medical advice. For your own health, talk to a doctor, nurse or pharmacist.
      </footer>
    </div>
  );
}
