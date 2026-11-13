import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { useMe } from "./auth";
import AppShell from "./components/AppShell";
import { useI18n } from "./i18n";
import Admin from "./pages/Admin";
import ChangePassword from "./pages/ChangePassword";
import CourseDashboard from "./pages/CourseDashboard";
import CoursePicker from "./pages/CoursePicker";
import Join from "./pages/Join";
import Login from "./pages/Login";

/** Route guard driven by GET /auth/me: login first, then a pending password change. Wraps the pages in the shell. */
function Guard() {
  const { data: me, isLoading, isError } = useMe();
  const location = useLocation();
  const { t } = useI18n();
  if (isLoading) return <p className="p-8 text-muted-foreground">{t("app.loading")}</p>;
  if (isError) return <p className="p-8 text-destructive">{t("app.unreachable")}</p>;
  if (!me) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (me.must_change_password && location.pathname !== "/change-password") {
    return <Navigate to="/change-password" replace />;
  }
  return <AppShell me={me} />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/join" element={<Join />} />
      <Route element={<Guard />}>
        <Route path="/change-password" element={<ChangePassword />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="/courses" element={<CoursePicker />} />
        <Route path="/courses/:courseId/:tab?" element={<CourseDashboard />} />
      </Route>
      <Route path="*" element={<Navigate to="/courses" replace />} />
    </Routes>
  );
}
