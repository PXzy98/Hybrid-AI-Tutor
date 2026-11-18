import { Loader2, RotateCw, WifiOff } from "lucide-react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { useMe } from "./auth";
import AppShell from "./components/AppShell";
import { BrandMark } from "./components/shell/Sidebar";
import { Button } from "./components/ui/button";
import { Toaster } from "./components/ui/sonner";
import { useI18n } from "./i18n";
import Admin from "./pages/Admin";
import ChangePassword from "./pages/ChangePassword";
import CourseDashboard from "./pages/CourseDashboard";
import CoursePicker from "./pages/CoursePicker";
import Join from "./pages/Join";
import Login from "./pages/Login";

/** Route guard driven by GET /auth/me: login first, then a pending password change. Wraps the pages in the shell. */
function Guard() {
  const { data: me, isLoading, isError, refetch, isFetching } = useMe();
  const location = useLocation();
  const { t } = useI18n();
  if (isLoading) {
    return (
      <div aria-busy="true" className="flex h-dvh flex-col items-center justify-center gap-4">
        <BrandMark className="size-10" />
        <Loader2 aria-hidden className="size-5 animate-spin motion-reduce:animate-none text-muted-foreground" />
        <span className="sr-only">{t("app.loading")}</span>
      </div>
    );
  }
  if (isError) {
    return (
      <div className="flex h-dvh flex-col items-center justify-center gap-3 px-4 text-center">
        <span aria-hidden className="flex size-10 items-center justify-center rounded-full bg-muted text-muted-foreground"><WifiOff className="size-5" /></span>
        <p role="alert" className="max-w-sm text-sm">{t("app.unreachable")}</p>
        <Button type="button" variant="outline" size="sm" loading={isFetching} onClick={() => void refetch()}>
          <RotateCw aria-hidden />{t("app.retry")}
        </Button>
      </div>
    );
  }
  if (!me) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (me.must_change_password && location.pathname !== "/change-password") {
    return <Navigate to="/change-password" replace />;
  }
  return <AppShell me={me} />;
}

export default function App() {
  return (
    <>
    <Toaster />
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
    </>
  );
}
