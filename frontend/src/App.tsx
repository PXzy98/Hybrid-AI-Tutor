import type { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { homeFor, useMe } from "./auth";
import Layout from "./components/Layout";
import { useI18n } from "./i18n";
import Admin from "./pages/Admin";
import ChangePassword from "./pages/ChangePassword";
import Chat from "./pages/Chat";
import Login from "./pages/Login";
import Onboarding from "./pages/Onboarding";
import WhatIKnow from "./pages/WhatIKnow";

type Role = "student" | "instructor";

/** Route guard driven by GET /auth/me: login first, then a pending password change, then the role. */
function Guard({ role, children }: { role?: Role; children: ReactNode }) {
  const { data: me, isLoading, isError } = useMe();
  const location = useLocation();
  const { t } = useI18n();
  if (isLoading) return <p className="p-8 text-slate-600">{t("app.loading")}</p>;
  if (isError) return <p className="p-8 text-red-700">{t("app.unreachable")}</p>;
  if (!me) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (me.must_change_password && location.pathname !== "/change-password") {
    return <Navigate to="/change-password" replace />;
  }
  if (role && me.role !== role) return <Navigate to={homeFor(me)} replace />;
  return <Layout me={me}>{children}</Layout>;
}

function Home() {
  const { data: me, isLoading } = useMe();
  if (isLoading) return null;
  return <Navigate to={me ? homeFor(me) : "/login"} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/change-password" element={<Guard><ChangePassword /></Guard>} />
      <Route path="/start" element={<Guard role="student"><Onboarding /></Guard>} />
      <Route path="/chat" element={<Guard role="student"><Chat /></Guard>} />
      <Route path="/me" element={<Guard role="student"><WhatIKnow /></Guard>} />
      <Route path="/admin/*" element={<Guard role="instructor"><Admin /></Guard>} />
      <Route path="*" element={<Home />} />
    </Routes>
  );
}
